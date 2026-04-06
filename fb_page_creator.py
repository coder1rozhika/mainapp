#!/usr/bin/env python3
"""
Facebook Page Creator via Meta Business Suite Mobile API
Uses curl_cffi for TLS fingerprint impersonation, pyotp for TOTP 2FA
"""

import hashlib
import json
import time
import uuid
import sys

import pyotp
from curl_cffi import requests

FB_API_KEY = "256002347743983"
FB_API_SECRET = "374e60f8b9bb6b8cbb30f78030438895"

BIZ_APP_ID = "121876164619130"
BIZ_CLIENT_TOKEN = "1ab2c5c902faedd339c14b2d58e929dc"

AUTH_URL = "https://b-api.facebook.com/method/auth.login"
GRAPH_URL_TEMPLATE = "https://graph.facebook.com/{uid}/accounts"

DEVICE_ID = str(uuid.uuid4())
ADID = str(uuid.uuid4())

USER_AGENT = (
    "[FBAN/FBBusinessSuiteAndroid;FBAV/547.0.0.40.109;FBBV/922914753;"
    "FBDM/{density=2.0,width=1080,height=1920};FBLC/en_US;FBCR/;"
    "FBMF/Google;FBBD/google;FBPN/com.facebook.pages.app;FBDV/Pixel 4;"
    "FBSV/13.0;FBLR/0;FBBK/1;FBCA/arm64-v8a:;]"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Content-Type": "application/x-www-form-urlencoded",
    "X-FB-Connection-Type": "WIFI",
    "X-FB-HTTP-Engine": "Liger",
    "X-FB-Client-IP": "True",
    "X-FB-Server-Cluster": "True",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "en_US",
}


def fb_sig(params: dict) -> dict:
    """Return a signed copy of the provided parameters."""
    params_str = "".join(f"{key}={value}" for key, value in sorted(params.items()))
    sig = hashlib.md5((params_str + FB_API_SECRET).encode("utf-8")).hexdigest()
    signed = params.copy()
    signed["sig"] = sig
    return signed


def _parse_json_response(response) -> dict:
    """Parse a JSON API response and include raw text on decode failures."""
    try:
        return response.json()
    except Exception:
        return {
            "error": "invalid_json_response",
            "status_code": response.status_code,
            "text": response.text,
        }


def _print_json(prefix: str, payload: dict) -> None:
    """Pretty-print a JSON payload for debugging."""
    print(prefix)
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _load_error_data(error_data):
    """Normalize Facebook error_data values into a dictionary when possible."""
    if isinstance(error_data, dict):
        return error_data
    if isinstance(error_data, str) and error_data.strip():
        try:
            return json.loads(error_data)
        except json.JSONDecodeError:
            return {"raw_error_data": error_data}
    return {}


def _base_auth_params(email: str, password: str, credentials_type: str) -> dict:
    """Build the shared auth.login parameter set."""
    return {
        "api_key": FB_API_KEY,
        "email": email,
        "password": password,
        "credentials_type": credentials_type,
        "generate_session_cookies": "1",
        "generate_machine_id": "1",
        "format": "json",
        "locale": "en_US",
        "client_country_code": "US",
        "fb_api_req_friendly_name": "authenticate",
        "fb_api_caller_class": "com.facebook.auth.login.AuthenticationClient",
        "method": "auth.login",
        "device_id": DEVICE_ID,
        "adid": ADID,
        "source": "login",
        "meta_inf_fbmeta": "",
        "currently_logged_in_userid": "0",
        "try_num": "1",
    }


def login(session, email, password) -> dict:
    """Perform the initial auth.login request using password credentials."""
    payload = fb_sig(_base_auth_params(email, password, "password"))
    response = None
    try:
        response = session.post(
            AUTH_URL,
            data=payload,
            headers=HEADERS,
            impersonate="chrome120",
        )
        return _parse_json_response(response)
    except Exception as exc:
        print(f"[-] login request failed: {exc}", file=sys.stderr)
        if response is not None:
            _print_json("[debug] login response:", _parse_json_response(response))
        raise


def submit_2fa(session, email, totp_code, login_first_factor, uid, machine_id) -> dict:
    """Submit a two-factor auth.login request using a TOTP code."""
    payload = _base_auth_params(email, totp_code, "two_factor")
    payload.update(
        {
            "twofactor_code": totp_code,
            "first_factor": login_first_factor,
            "userid": uid,
            "machine_id": machine_id,
            "error_detail_type": "button_with_disabled",
        }
    )
    payload = fb_sig(payload)
    response = None
    try:
        response = session.post(
            AUTH_URL,
            data=payload,
            headers=HEADERS,
            impersonate="chrome120",
        )
        return _parse_json_response(response)
    except Exception as exc:
        print(f"[-] 2FA request failed: {exc}", file=sys.stderr)
        if response is not None:
            _print_json("[debug] 2FA response:", _parse_json_response(response))
        raise


def get_totp_code(secret: str) -> str:
    """Generate a TOTP code, waiting for the next interval if expiry is imminent."""
    totp = pyotp.TOTP(secret)
    remaining = totp.interval - (int(time.time()) % totp.interval)
    if remaining < 5:
        wait_for = remaining + 1
        print(f"[*] Current TOTP expires in {remaining}s; waiting {wait_for}s for a fresh code...")
        time.sleep(wait_for)
    return totp.now()


def create_page(session, access_token, uid, page_name, category="INTERNET_COMPANY") -> dict:
    """Create a Facebook Page under the authenticated account."""
    payload = {
        "name": page_name,
        "category_enum": category,
        "access_token": access_token,
    }
    response = None
    try:
        response = session.post(
            GRAPH_URL_TEMPLATE.format(uid=uid),
            data=payload,
            headers=HEADERS,
            impersonate="chrome120",
        )
        return _parse_json_response(response)
    except Exception as exc:
        print(f"[-] create_page request failed: {exc}", file=sys.stderr)
        if response is not None:
            _print_json("[debug] create_page response:", _parse_json_response(response))
        raise


def main() -> None:
    """Run the login -> 2FA -> page creation flow."""
    account = "61573675646875|HEbb@#19592752285343|WJNGTSBBDWFWUAXLMOZCYZ5MWLWT3664"
    try:
        account_uid, password, totp_secret = account.split("|", 2)
    except ValueError:
        print("[-] Invalid account string. Expected uid|password|2fa_secret.")
        sys.exit(1)

    session = requests.Session()
    session.headers.update(HEADERS)

    print("[*] Step 1/3: Logging in with password...")
    try:
        login_response = login(session, account_uid, password)
    except Exception:
        sys.exit(1)

    _print_json("[debug] login response:", login_response)

    access_token = login_response.get("access_token")
    current_uid = login_response.get("uid") or account_uid

    if access_token:
        print("[+] Password login succeeded without 2FA challenge.")
    else:
        error_code = login_response.get("error_code")
        if error_code == 1:
            print("[-] Error 1: IP may be blocked. Try from residential/mobile network.")
            sys.exit(1)
        if error_code != 406:
            print("[-] Login failed unexpectedly.")
            _print_json("[debug] unexpected login payload:", login_response)
            sys.exit(1)

        error_data = _load_error_data(login_response.get("error_data"))
        login_first_factor = error_data.get("login_first_factor")
        machine_id = error_data.get("machine_id")
        current_uid = error_data.get("uid") or current_uid

        if not all([login_first_factor, machine_id, current_uid]):
            print("[-] 2FA challenge data incomplete.")
            _print_json("[debug] parsed error_data:", error_data)
            sys.exit(1)

        print("[*] Step 2/3: Submitting TOTP 2FA challenge...")
        totp_code = get_totp_code(totp_secret)
        print("[*] Generated fresh TOTP code.")

        try:
            twofa_response = submit_2fa(
                session,
                account_uid,
                totp_code,
                login_first_factor,
                current_uid,
                machine_id,
            )
        except Exception:
            sys.exit(1)

        _print_json("[debug] 2FA response:", twofa_response)

        access_token = twofa_response.get("access_token")
        current_uid = twofa_response.get("uid") or current_uid
        if not access_token:
            print("[-] 2FA failed.")
            _print_json("[debug] 2FA failure payload:", twofa_response)
            sys.exit(1)
        print("[+] 2FA completed successfully.")

    print("[*] Step 3/3: Creating page 'My Business Page'...")
    try:
        page_response = create_page(session, access_token, current_uid, "My Business Page")
    except Exception:
        sys.exit(1)

    _print_json("[debug] create_page response:", page_response)

    if page_response.get("id") or page_response.get("success"):
        print("[+] Page creation request succeeded.")
        return

    print("[-] Page creation request returned an error payload.")
    _print_json("[debug] page creation payload:", page_response)
    sys.exit(1)


if __name__ == "__main__":
    main()
