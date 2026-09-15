import requests
from config_manager import config_mgr

class APIClient:
    def __init__(self):
        self._session = requests.Session()
        # Disable system environment proxies that trigger PermissionError (13: Permission denied) on Windows
        self._session.trust_env = False
        self._session.headers.update({
            "User-Agent": "QwikPrintAgent/1.0.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "application/json"
        })
        self.last_subscription_error = None

    def _request(self, method: str, url: str, **kwargs):
        """Executes HTTP request with proxy bypass and 127.0.0.1 loopback fallback."""
        kwargs.setdefault("timeout", 10)
        try:
            return self._session.request(method, url, **kwargs)
        except (requests.exceptions.ConnectionError, OSError) as e:
            # Automatic fallback for localhost -> 127.0.0.1 if IPv6/localhost socket fails
            if "localhost" in url:
                alt_url = url.replace("localhost", "127.0.0.1")
                try:
                    return self._session.request(method, alt_url, **kwargs)
                except Exception:
                    pass
            raise e

    @property
    def server_url(self) -> str:
        return config_mgr.get("server_url", "http://localhost:8000").rstrip("/")

    @property
    def headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "X-Device-Id": config_mgr.get("device_id", ""),
            "X-Device-Token": config_mgr.get("device_token", "")
        }

    def verify_api_key(self, server_url: str, api_key: str) -> tuple[bool, str, dict]:
        """Verifies Shopkeeper API Key and auto-fetches 1 API = 1 PC credentials."""
        url = f"{server_url.rstrip('/')}/api/agent/verify-key"
        try:
            res = self._request("POST", url, json={"apiKey": api_key}, headers={"Content-Type": "application/json"}, timeout=10)
            data = res.json()
            if res.status_code == 200 and data.get("success"):
                return True, data.get("message", "API Key verified!"), data
            else:
                return False, data.get("error", "Invalid API Key"), {}
        except Exception as e:
            err_str = str(e)
            if "PermissionError" in err_str or "Permission denied" in err_str or "10013" in err_str:
                return False, (
                    "Windows Network Permission Error (Permission Denied).\n\n"
                    "Your Windows Firewall, Antivirus, or proxy setting is blocking Python socket connections.\n"
                    "Please allow QwikPrint Agent in Windows Defender / Antivirus or run as Administrator."
                ), {}
            return False, f"Connection failed: {err_str}", {}

    def register_device(self, server_url: str, shop_id: str, device_name: str, id_token: str) -> tuple[bool, str, dict]:
        """Registers device with shop owner credentials."""
        url = f"{server_url.rstrip('/')}/api/agent/register-device"
        try:
            res = self._request(
                "POST",
                url,
                json={"shopId": shop_id, "deviceName": device_name, "appVersion": "1.0.0-python"},
                headers={"Authorization": f"Bearer {id_token}", "Content-Type": "application/json"},
                timeout=10
            )
            data = res.json()
            if res.status_code == 200 and data.get("success"):
                return True, "Device registered successfully!", data
            else:
                return False, data.get("error", "Registration failed"), {}
        except Exception as e:
            return False, f"Connection error: {str(e)}", {}

    def send_heartbeat(self, printer_status: str = "ready") -> bool:
        """Sends periodic heartbeat to web server."""
        if not config_mgr.is_configured():
            return False
        url = f"{self.server_url}/api/agent/heartbeat"
        try:
            res = self._request(
                "POST",
                url,
                json={
                    "deviceId": config_mgr.get("device_id"),
                    "shopId": config_mgr.get("shop_id"),
                    "deviceName": config_mgr.get("device_name"),
                    "appVersion": "1.0.0-python",
                    "printerStatus": printer_status
                },
                headers=self.headers,
                timeout=5
            )
            if res.status_code == 200:
                self.last_subscription_error = None
                return True
            elif res.status_code == 403:
                try:
                    self.last_subscription_error = res.json().get("detail", "Subscription Locked")
                except Exception:
                    self.last_subscription_error = "Subscription Locked"
                return False
            return False
        except Exception:
            return False

    def fetch_queue(self) -> tuple[list, list]:
        """Returns (queued_jobs, cash_pending_jobs)."""
        if not config_mgr.is_configured():
            return [], []
        url = f"{self.server_url}/api/agent/queue"
        try:
            res = self._request("GET", url, headers=self.headers, timeout=5)
            if res.status_code == 200:
                self.last_subscription_error = None
                data = res.json()
                return data.get("jobs", []), data.get("cashPendingJobs", [])
            elif res.status_code == 403:
                try:
                    self.last_subscription_error = res.json().get("detail", "Subscription Locked")
                except Exception:
                    self.last_subscription_error = "Subscription Locked"
                print(f"[API Error] Subscription locked: {self.last_subscription_error}")
                return [], []
            return [], []
        except Exception as e:
            print(f"[API Error] Fetch queue failed: {e}")
            return [], []

    def claim_job(self, job_id: str) -> tuple[bool, dict]:
        """Claims print job for this device."""
        url = f"{self.server_url}/api/agent/claim-job"
        try:
            res = self._request("POST", url, json={"jobId": job_id}, headers=self.headers, timeout=5)
            data = res.json()
            if res.status_code == 200 and data.get("success"):
                return True, data.get("job", {})
            return False, {}
        except Exception as e:
            print(f"[API Error] Claim job failed: {e}")
            return False, {}

    def get_download_url(self, job_id: str) -> str:
        """Gets pre-signed download URL for job file."""
        url = f"{self.server_url}/api/agent/download-url?jobId={job_id}"
        try:
            res = self._request("GET", url, headers=self.headers, timeout=8)
            if res.status_code == 200:
                data = res.json()
                return data.get("downloadUrl", "")
            return ""
        except Exception as e:
            print(f"[API Error] Get download URL failed: {e}")
            return ""

    def update_status(self, job_id: str, status: str, error_msg: str = None) -> bool:
        """Updates job status: DOWNLOADING -> PRINTING -> PRINTED / PRINT_FAILED."""
        url = f"{self.server_url}/api/agent/update-status"
        try:
            res = self._request(
                "POST",
                url,
                json={"jobId": job_id, "status": status, "error": error_msg},
                headers=self.headers,
                timeout=8
            )
            return res.status_code == 200
        except Exception as e:
            print(f"[API Error] Update status failed: {e}")
            return False

    def confirm_cash_payment(self, job_id: str) -> tuple[bool, str]:
        """Confirms cash payment for a job."""
        url = f"{self.server_url}/api/jobs/{job_id}/confirm-cash"
        try:
            res = self._request("POST", url, headers=self.headers, timeout=8)
            data = res.json()
            if res.status_code == 200 and data.get("success"):
                return True, "Cash payment approved!"
            return False, data.get("error", "Cash approval failed")
        except Exception as e:
            return False, f"Network error: {str(e)}"

    def reject_cash_payment(self, job_id: str) -> tuple[bool, str]:
        """Rejects cash payment for a job."""
        url = f"{self.server_url}/api/jobs/{job_id}/reject-cash"
        try:
            res = self._request("POST", url, headers=self.headers, timeout=8)
            data = res.json()
            if res.status_code == 200 and data.get("success"):
                return True, "Cash payment rejected"
            return False, data.get("error", "Cash rejection failed")
        except Exception as e:
            return False, f"Network error: {str(e)}"

    def update_pricing(self, bw_rate: float, color_rate: float, duplex_discount: float) -> tuple[bool, str]:
        """Updates shop pricing rates on server."""
        url = f"{self.server_url}/api/agent/pricing"
        shop_id = config_mgr.get("shop_id")
        try:
            res = self._request(
                "POST",
                url,
                json={
                    "shopId": shop_id,
                    "bwRate": bw_rate,
                    "colorRate": color_rate,
                    "duplexDiscount": duplex_discount
                },
                headers=self.headers,
                timeout=8
            )
            data = res.json()
            if res.status_code == 200 and data.get("success"):
                config_mgr.save_config({
                    "bw_rate": bw_rate,
                    "color_rate": color_rate,
                    "duplex_discount": duplex_discount
                })
                return True, data.get("message", "Pricing updated successfully!")
            return False, data.get("error", "Pricing update failed")
        except Exception as e:
            return False, f"Network error: {str(e)}"

    def update_paper_rates(self, paper_rates: list) -> tuple[bool, str]:
        """Updates shop paper rates (max 5 paper sizes) on server."""
        url = f"{self.server_url}/api/agent/paper-rates"
        shop_id = config_mgr.get("shop_id")
        try:
            res = self._request(
                "POST",
                url,
                json={"shopId": shop_id, "paperRates": paper_rates[:5]},
                headers=self.headers,
                timeout=8
            )
            data = res.json()
            if res.status_code == 200 and data.get("success"):
                return True, "Paper sizes & rates updated successfully!"
            return False, data.get("error", "Paper rates update failed")
        except Exception as e:
            return False, f"Network error: {str(e)}"

api_client = APIClient()
