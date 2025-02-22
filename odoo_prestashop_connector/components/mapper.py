# components/mapper.py
from odoo.addons.component.core import AbstractComponent
from odoo.addons.connector.components.mapper import ImportMapper


class PrestashopImportMapper(AbstractComponent):
    """ Base Import Mapper for PrestaShop """

    _name = 'prestashop.import.mapper'
    _inherit = ['base.import.mapper']
    _usage = 'import.mapper'

    def _get_language_id(self, record, language_field=None):
        """ Get Odoo language to use from PrestaShop lang.
        Returns `False` if not found.
        """
        if not language_field:
            language_field = 'id_lang'

        prestashop_lang = record.get(language_field)
        if not prestashop_lang:
            return False

        binder = self.binder_for('prestashop.res.lang')
        if not binder:
            return False

        return binder.to_internal(prestashop_lang)

    def _split_per_language(self, record, fields):
        """ Split a record values by language.
        :param record: PrestaShop record
        :param fields: list of fields to split
        :return: list of dictionaries
        """
        result = []
        languages = record.get('associations', {}).get('languages', [])
        if not languages:
            return [record]

        for language in languages:
            lang_record = record.copy()
            for field in fields:
                if field in record and hasattr(record[field], 'get'):
                    lang_record[field] = record[field].get(language['id'])
            result.append(lang_record)

        return result