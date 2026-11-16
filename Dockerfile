# Odoo 20 + DKM custom addons, built by Easypanel from this repository.
FROM odoo:20.0-20261112

USER root
# The base image's en_US.UTF-8 locale is not generated; avoids perl warnings
# from the PostgreSQL client wrappers.
ENV LANG=C.UTF-8
# Python libraries required by base_accounting_kit that the official image
# does not ship (openpyxl and xlsxwriter already come with Odoo).
RUN pip3 install --no-cache-dir --break-system-packages \
        ofxparse==0.21 qifparse==0.5

# Not /mnt/extra-addons: the base image declares that path a VOLUME, which
# can shadow the baked-in modules with a stale volume.
COPY --chown=odoo:odoo . /opt/dkm-addons/
COPY --chmod=755 deploy/entrypoint-dkm.sh /usr/local/bin/entrypoint-dkm.sh
COPY --chmod=644 deploy/bootstrap.py /usr/local/share/dkm-bootstrap.py

USER odoo
EXPOSE 8069 8072
ENTRYPOINT ["/usr/local/bin/entrypoint-dkm.sh"]
CMD ["odoo"]
