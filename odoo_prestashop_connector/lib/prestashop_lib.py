from prestapyt import PrestaShopWebService as BasePrestaShopWebService
from packaging import version


class PrestaShopWebService(BasePrestaShopWebService):
    def _check_version(self, version_str):
        """Override version checking to use packaging.version"""
        if not version_str:
            return
        try:
            current_version = version.parse(version_str)
            min_version = version.parse(self.MIN_COMPATIBLE_VERSION)
            max_version = version.parse(self.MAX_COMPATIBLE_VERSION)

            if not (min_version <= current_version <= max_version):
                raise Exception(
                    "Version mismatch: this client only supports PrestaShop Webservice from "
                    "%s to %s but tried to connect to %s" % (
                        self.MIN_COMPATIBLE_VERSION,
                        self.MAX_COMPATIBLE_VERSION,
                        version_str
                    )
                )
        except Exception as e:
            # Log but don't raise for version issues
            pass