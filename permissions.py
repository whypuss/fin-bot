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
                if self.owner_id not in data:
                    data[self.owner_id] = {"role": "owner", "note": "Super Admin"}
                    self._save(data)
                return data
        except Exception:
            return {self.owner_id: {"role": "owner", "note": "Super Admin"}}

    def _save(self, data=None):
        if data is None:
            data = self.perms
        with open(PERMS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def is_authorized(self, user_id: int) -> bool:
        uid = str(user_id)
        return uid in self.perms

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
        if uid == self.owner_id:
            return False  # 不能撤銷 Owner
        if uid in self.perms:
            del self.perms[uid]
            self._save()
            return True
        return False

    def list_users(self):
        return self.perms
