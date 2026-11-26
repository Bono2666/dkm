# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class DkmActivity(models.Model):
    """A mosque activity (Qurban 1447 H, Ramadhan 1447 H, ...): its budget per
    pos, and the receipts and bills recorded for it."""
    _name = 'dkm.activity'
    _description = "Kegiatan"
    _inherit = ['mail.thread']
    _order = 'date_start desc, id desc'

    name = fields.Char("Kegiatan", required=True, tracking=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    date_start = fields.Date("Mulai", tracking=True)
    date_end = fields.Date("Selesai", tracking=True)
    division_id = fields.Many2one('dkm.division', string="Penanggung Jawab", tracking=True)
    state = fields.Selection([
        ('draft', "Rencana"),
        ('open', "Berjalan"),
        ('done', "Selesai"),
        ('cancel', "Dibatalkan"),
    ], string="Status", default='draft', required=True, tracking=True)
    note = fields.Text("Keterangan")
    budget_line_ids = fields.One2many('dkm.activity.budget', 'activity_id',
                                      string="Anggaran", copy=True)
    income_budget_ids = fields.One2many(
        'dkm.activity.budget', 'activity_id', string="Anggaran Penerimaan",
        domain=[('type', '=', 'income')], context={'default_type': 'income'})
    expense_budget_ids = fields.One2many(
        'dkm.activity.budget', 'activity_id', string="Anggaran Pengeluaran",
        domain=[('type', '=', 'expense')], context={'default_type': 'expense'})
    budget_income = fields.Monetary("Target Penerimaan", compute='_compute_budget')
    budget_expense = fields.Monetary("Anggaran Pengeluaran", compute='_compute_budget')
    amount_income = fields.Monetary("Penerimaan", compute='_compute_amounts')
    amount_expense = fields.Monetary("Pengeluaran", compute='_compute_amounts')
    amount_balance = fields.Monetary("Sisa Dana", compute='_compute_amounts')
    transaction_count = fields.Integer("Transaksi", compute='_compute_amounts')

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for activity in self:
            if activity.date_start and activity.date_end \
                    and activity.date_end < activity.date_start:
                raise UserError("Tanggal selesai tidak boleh sebelum tanggal mulai.")

    @api.depends('budget_line_ids.planned_amount', 'budget_line_ids.type')
    def _compute_budget(self):
        for activity in self:
            lines = activity.budget_line_ids
            activity.budget_income = sum(lines.filtered(
                lambda b: b.type == 'income').mapped('planned_amount'))
            activity.budget_expense = sum(lines.filtered(
                lambda b: b.type == 'expense').mapped('planned_amount'))

    def _compute_amounts(self):
        totals = {
            activity.id: (income, expense, balance, count)
            for activity, income, expense, balance, count
            in self.env['dkm.activity.report'].sudo()._read_group(
                [('activity_id', 'in', self.ids)], ['activity_id'],
                ['income:sum', 'expense:sum', 'balance:sum', '__count'])
        }
        for activity in self:
            income, expense, balance, count = totals.get(activity.id, (0.0, 0.0, 0.0, 0))
            activity.amount_income = income
            activity.amount_expense = expense
            activity.amount_balance = balance
            activity.transaction_count = count

    def action_open(self):
        self.filtered(lambda a: a.state == 'draft').state = 'open'
        return True

    def action_done(self):
        self.filtered(lambda a: a.state == 'open').state = 'done'
        return True

    def action_cancel(self):
        for activity in self:
            if activity.transaction_count:
                raise UserError("Kegiatan yang sudah punya transaksi tidak bisa dibatalkan; "
                                "tandai Selesai saja.")
            activity.state = 'cancel'
        return True

    def action_draft(self):
        self.filtered(lambda a: a.state in ('done', 'cancel')).state = 'open'
        return True

    def action_view_transactions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f"Transaksi {self.name}",
            'res_model': 'dkm.activity.report',
            'view_mode': 'list,pivot',
            'domain': [('activity_id', '=', self.id)],
            'context': {'search_default_group_type': 1},
        }

    def action_print(self):
        return self.env.ref('dkm_kegiatan.action_report_activity').report_action(self)

    def _dkm_report_data(self):
        """Rows for the PDF: budget vs actual per pos (plus unbudgeted
        amounts by category/account) and the posted transactions."""
        self.ensure_one()
        lines = self.env['dkm.activity.report'].sudo().search(
            [('activity_id', '=', self.id)], order='date, id')

        def rows(kind):
            result = []
            for budget in self.budget_line_ids.filtered(lambda b: b.type == kind):
                result.append({
                    'name': budget.name, 'planned': budget.planned_amount,
                    'actual': sum(lines.filtered(lambda l: l.budget_id == budget).mapped(kind)),
                })
            other = {}
            for line in lines.filtered(lambda l: not l.budget_id and l[kind]):
                key = line.product_id.name or line.account_id.name
                other[key] = other.get(key, 0.0) + line[kind]
            result += [{'name': name, 'planned': 0.0, 'actual': amount}
                       for name, amount in other.items()]
            return result

        income_rows, expense_rows = rows('income'), rows('expense')
        for row in income_rows + expense_rows:
            row['percent'] = round(row['actual'] / row['planned'] * 100) if row['planned'] else 0

        def total(items):
            return {'planned': sum(r['planned'] for r in items),
                    'actual': sum(r['actual'] for r in items)}

        return {
            'income_rows': income_rows,
            'expense_rows': expense_rows,
            'income_total': total(income_rows),
            'expense_total': total(expense_rows),
            'income_lines': lines.filtered('income'),
            'expense_lines': lines.filtered('expense'),
        }


class DkmActivityBudget(models.Model):
    _name = 'dkm.activity.budget'
    _description = "Pos Anggaran Kegiatan"
    _order = 'activity_id, sequence, id'

    activity_id = fields.Many2one('dkm.activity', required=True, ondelete='cascade',
                                  index=True)
    company_id = fields.Many2one(related='activity_id.company_id', store=True)
    currency_id = fields.Many2one(related='activity_id.currency_id')
    sequence = fields.Integer(default=10)
    type = fields.Selection([('income', "Penerimaan"), ('expense', "Pengeluaran")],
                            string="Jenis", required=True, default='expense')
    name = fields.Char("Pos", required=True)
    planned_amount = fields.Monetary("Anggaran")
    actual_amount = fields.Monetary("Realisasi", compute='_compute_actual')
    difference = fields.Monetary("Selisih", compute='_compute_actual',
                                 help="Anggaran dikurangi realisasi.")
    progress = fields.Float("Realisasi (%)", compute='_compute_actual')

    def _compute_actual(self):
        totals = {
            budget.id: (income, expense)
            for budget, income, expense in self.env['dkm.activity.report'].sudo()._read_group(
                [('budget_id', 'in', self.ids)], ['budget_id'], ['income:sum', 'expense:sum'])
        }
        for budget in self:
            income, expense = totals.get(budget.id, (0.0, 0.0))
            budget.actual_amount = income if budget.type == 'income' else expense
            budget.difference = budget.planned_amount - budget.actual_amount
            budget.progress = (budget.actual_amount / budget.planned_amount * 100.0
                               if budget.planned_amount else 0.0)

    @api.depends('name', 'type')
    def _compute_display_name(self):
        for budget in self:
            kind = "Penerimaan" if budget.type == 'income' else "Pengeluaran"
            budget.display_name = f"{budget.name} ({kind})"
