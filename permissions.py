import json
import os

PERMS_FILE = os.path.join(os.path.dirname(__file__), "permissions.json")

class PermissionManager:
    def __init__(self, owner_id: int):
        self.owner_id = str(owner_id)
        self.perms = self._load()

    def _load(self):
        default = {
            "_meta": {
                "public_mode": True,  # 預設允許全體 TG 用戶使用金融投研
                "pause_reason": "管理員維護中"
            },
            self.owner_id: {
                "role": "owner",
                "note": "Super Admin"
            }
        }
        if not os.path.exists(PERMS_FILE):
            self._save(default)
            return default
        try:
            with open(PERMS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "_meta" not in data:
                    data["_meta"] = {"public_mode": True, "pause_reason": "管理員維護中"}
                if self.owner_id not in data:
                    data[self.owner_id] = {"role": "owner", "note": "Super Admin"}
                self._save(data)
                return data
        except Exception:
            return default

    def _save(self, data=None):
        if data is None:
            data = self.perms
        with open(PERMS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def is_public_mode(self) -> bool:
        """是否對外開放（允許所有普通 TG 用戶使用金融服務）"""
        return self.perms.get("_meta", {}).get("public_mode", True)

    def set_public_mode(self, allow_public: bool, reason: str = "") -> bool:
        """切換對外開放狀態"""
        if "_meta" not in self.perms:
            self.perms["_meta"] = {}
        self.perms["_meta"]["public_mode"] = allow_public
        if reason:
            self.perms["_meta"]["pause_reason"] = reason
        self._save()
        return allow_public

    def toggle_public_mode(self) -> bool:
        """一鍵切換：臨時關閉對外開放 / 恢復對外開放"""
        current = self.is_public_mode()
        new_state = not current
        self.set_public_mode(new_state)
        return new_state

    # 向後相容別名
    def is_paused(self) -> bool:
        return not self.is_public_mode()

    def toggle_paused(self) -> bool:
        return not self.toggle_public_mode()

    def is_authorized(self, user_id: int) -> bool:
        """
        授權驗證（嚴格沙箱原則）：
        1. Owner 永遠具有所有權限
        2. 若處於對外開放狀態 (public_mode=True)：允許所有 TG 用戶使用純金融服務
        3. 若已臨時關閉對外開放 (public_mode=False)：只有 Owner 及白名單用戶可用
        """
        uid = str(user_id)
        if self.is_owner(user_id):
            return True
        if self.is_public_mode():
            return True
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
            return False
        if uid in self.perms:
            del self.perms[uid]
            self._save()
            return True
        return False

    def list_users(self) -> dict:
        """列出所有已註冊用戶（排除系統旗標 _meta）"""
        return {k: v for k, v in self.perms.items() if k != "_meta"}
