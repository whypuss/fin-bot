import json
import os

PERMS_FILE = os.path.join(os.path.dirname(__file__), "permissions.json")

class PermissionManager:
    def __init__(self, owner_id: int):
        self.owner_id = str(owner_id)
        self.perms = self._load()

    def _load(self):
        if not os.path.exists(PERMS_FILE):
            default = {
                "_meta": {
                    "is_paused": False,
                    "pause_reason": "管理員維護中"
                },
                self.owner_id: {
                    "role": "owner",
                    "note": "Super Admin"
                }
            }
            self._save(default)
            return default
        try:
            with open(PERMS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "_meta" not in data:
                    data["_meta"] = {"is_paused": False, "pause_reason": "管理員維護中"}
                if self.owner_id not in data:
                    data[self.owner_id] = {"role": "owner", "note": "Super Admin"}
                self._save(data)
                return data
        except Exception:
            return {
                "_meta": {"is_paused": False, "pause_reason": "管理員維護中"},
                self.owner_id: {"role": "owner", "note": "Super Admin"}
            }

    def _save(self, data=None):
        if data is None:
            data = self.perms
        with open(PERMS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def is_paused(self) -> bool:
        """檢查 Bot 是否處於臨時關閉/維護狀態"""
        return self.perms.get("_meta", {}).get("is_paused", False)

    def set_paused(self, paused: bool, reason: str = "管理員臨時維護中") -> bool:
        """手動設定暫停狀態"""
        if "_meta" not in self.perms:
            self.perms["_meta"] = {}
        self.perms["_meta"]["is_paused"] = paused
        self.perms["_meta"]["pause_reason"] = reason
        self._save()
        return paused

    def toggle_paused(self) -> bool:
        """一鍵切換臨時關閉/恢復開放狀態，回傳切換後的新狀態"""
        current = self.is_paused()
        new_state = not current
        self.set_paused(new_state)
        return new_state

    def is_authorized(self, user_id: int) -> bool:
        """
        授權驗證：
        1. Owner 擁有最高特權，即使臨時關閉也永遠授權（以維護與解鎖）
        2. 當 Bot 處於臨時關閉 (is_paused) 狀態時，非 Owner 一律攔截
        3. 正常狀態下，檢查是否在授權名單中
        """
        uid = str(user_id)
        if self.is_owner(user_id):
            return True
        if self.is_paused():
            return False
        return uid in self.perms and uid != "_meta"

    def is_owner(self, user_id: int) -> bool:
        return str(user_id) == self.owner_id

    def add_user(self, user_id: int, role: str = "user", note: str = "") -> bool:
        uid = str(user_id)
        self.perms[uid] = {
            "role": role,
            "note": note
        }
        self._save()
        return True

    def revoke_user(self, user_id: int) -> bool:
        uid = str(user_id)
        if uid == self.owner_id or uid == "_meta":
            return False  # 不能撤銷 Owner 或內部旗標
        if uid in self.perms:
            del self.perms[uid]
            self._save()
            return True
        return False

    def list_users(self) -> dict:
        """列出所有實際授權用戶（排除系統旗標 _meta）"""
        return {k: v for k, v in self.perms.items() if k != "_meta"}
