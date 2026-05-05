import ssl
import warnings
import requests
import urllib3
from requests.adapters import HTTPAdapter


def make_api_session() -> requests.Session:
    """Return a requests.Session compatible with corporate proxy SSL inspection.

    Corporate networks (e.g. SAP) replace server certificates with ones signed
    by an internal CA that Python's certifi bundle does not trust, causing
    CERTIFICATE_VERIFY_FAILED.  Since the destination endpoints are known API
    servers, we disable certificate verification and suppress the warning.
    """
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    session = requests.Session()
    session.verify = False

    try:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.set_ciphers("DEFAULT:@SECLEVEL=1")

        class _TLSAdapter(HTTPAdapter):
            def init_poolmanager(self, *args, **kwargs):
                kwargs["ssl_context"] = ctx
                return super().init_poolmanager(*args, **kwargs)

            def proxy_manager_for(self, proxy, **kwargs):
                kwargs["ssl_context"] = ctx
                return super().proxy_manager_for(proxy, **kwargs)

        session.mount("https://", _TLSAdapter())
    except Exception:
        pass
    return session
