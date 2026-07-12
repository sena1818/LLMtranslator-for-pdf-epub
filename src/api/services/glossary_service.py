"""
术语表管理服务
"""
import json
from datetime import datetime
from pathlib import Path


class GlossaryService:
    """术语表管理服务"""

    def __init__(self):
        self.glossary_dir = Path("data/glossaries")
        self.glossary_dir.mkdir(parents=True, exist_ok=True)

    async def list_glossaries(self) -> list[dict]:
        """获取术语表列表"""
        result = []

        for file_path in self.glossary_dir.glob("*.json"):
            try:
                with open(file_path, encoding='utf-8') as f:
                    terms = json.load(f)

                result.append({
                    "id": file_path.stem,
                    "name": file_path.stem.replace("_", " ").title(),
                    "term_count": len(terms),
                    "updated_at": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
                })
            except Exception:
                continue

        return sorted(result, key=lambda x: x["updated_at"], reverse=True)

    async def get_glossary(self, glossary_id: str) -> dict | None:
        """获取术语表内容"""
        file_path = self.glossary_dir / f"{glossary_id}.json"

        if not file_path.exists():
            return None

        try:
            with open(file_path, encoding='utf-8') as f:
                terms = json.load(f)

            return {
                "id": glossary_id,
                "name": glossary_id.replace("_", " ").title(),
                "terms": terms
            }
        except Exception:
            return None

    async def create_glossary(self, name: str, terms: dict[str, str]) -> dict:
        """创建术语表"""
        glossary_id = name.lower().replace(" ", "_")
        file_path = self.glossary_dir / f"{glossary_id}.json"

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(terms, f, ensure_ascii=False, indent=2)

        return {
            "id": glossary_id,
            "name": name,
            "term_count": len(terms)
        }

    async def update_glossary(self, glossary_id: str, terms: dict[str, str]) -> bool:
        """更新术语表 (全量)"""
        file_path = self.glossary_dir / f"{glossary_id}.json"

        if not file_path.exists():
            return False

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(terms, f, ensure_ascii=False, indent=2)

        return True

    async def modify_terms(
        self,
        glossary_id: str,
        add: dict[str, str] = None,
        remove: list[str] = None
    ) -> int | None:
        """增量修改术语"""
        glossary = await self.get_glossary(glossary_id)
        if not glossary:
            return None

        terms = glossary["terms"]

        if add:
            terms.update(add)

        if remove:
            for key in remove:
                terms.pop(key, None)

        await self.update_glossary(glossary_id, terms)
        return len(terms)

    async def delete_glossary(self, glossary_id: str) -> bool:
        """删除术语表"""
        file_path = self.glossary_dir / f"{glossary_id}.json"

        if not file_path.exists():
            return False

        file_path.unlink()
        return True

    async def import_from_file(self, file_content: bytes, name: str) -> dict:
        """从文件导入"""
        terms = json.loads(file_content.decode('utf-8'))
        return await self.create_glossary(name, terms)

    async def export_to_file(self, glossary_id: str) -> Path | None:
        """导出到文件"""
        file_path = self.glossary_dir / f"{glossary_id}.json"

        if not file_path.exists():
            return None

        return file_path
