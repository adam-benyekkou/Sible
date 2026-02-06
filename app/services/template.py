import os
import logging
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger("uvicorn.error")

class TemplateService:
    BLUEPRINT_DIR = Path("app/blueprints")

    @staticmethod
    def list_templates() -> List[Dict[str, str]]:
        """
        Scans all files in BLUEPRINT_DIR and returns metadata.
        """
        templates = []
        if not TemplateService.BLUEPRINT_DIR.exists():
            return []

        for root, _, files in os.walk(TemplateService.BLUEPRINT_DIR):
            for file in files:
                if file.endswith((".yaml", ".yml")):
                    full_path = Path(root) / file
                    metadata = TemplateService._parse_metadata(full_path)
                    
                    # Compute relative path for ID/Name usage
                    rel_path = full_path.relative_to(TemplateService.BLUEPRINT_DIR)
                    name_id = str(rel_path).replace("\\", "/") # normalize for web
                    
                    templates.append({
                        "id": name_id,
                        "title": metadata.get("Title", name_id),
                        "description": metadata.get("Description", "No description provided"),
                        "category": metadata.get("Category", "Uncategorized"),
                        "author": metadata.get("Author", "Unknown")
                    })
        return templates

    @staticmethod
    def get_template_content(name_id: str) -> Optional[str]:
        """
        Returns the raw content of a template by its relative ID.
        """
        try:
            # Security check to prevent path traversal
            safe_path = (TemplateService.BLUEPRINT_DIR / name_id).resolve()
            if not str(safe_path).startswith(str(TemplateService.BLUEPRINT_DIR.resolve())):
                logger.warning(f"Attempted path traversal: {name_id}")
                return None
            
            if not safe_path.exists():
                return None
                
            return safe_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Error reading template {name_id}: {e}")
            return None

    @staticmethod
    def _parse_metadata(path: Path) -> Dict[str, str]:
        """
        Reads the first few lines looking for # Key: Value
        """
        metadata = {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                for match in range(10): # Only check first 10 lines
                    line = f.readline()
                    if not line: break
                    line = line.strip()
                    if line.startswith("#"):
                        # remove leading # and split
                        parts = line[1:].split(":", 1)
                        if len(parts) == 2:
                            key = parts[0].strip()
                            value = parts[1].strip()
                            metadata[key] = value
        except Exception as e:
            logger.error(f"Failed to parse metadata for {path}: {e}")
        return metadata
