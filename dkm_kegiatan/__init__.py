# -*- coding: utf-8 -*-
from . import models


def post_init_hook(env):
    env['dkm.masjid.setup']._setup_activity_category()
