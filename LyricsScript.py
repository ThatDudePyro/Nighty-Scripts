def lyrics():
    import asyncio
    import aiohttp
    import json
    import os
    import re
    import time
    from pathlib import Path
    from typing import Dict, List, Tuple, Optional, Any
    
    CONFIG_PATH = Path(os.path.expandvars(r"%APPDATA%\Nighty Selfbot\data\scripts\json\LyricsConfig.json"))
    lyrics_cache: Dict[str, Dict[str, Any]] = {}
    CACHE_EXPIRY = 3600

    def load_config() -> Dict[str, Any]:
        try:
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            if CONFIG_PATH.exists():
                with open(CONFIG_PATH, "r", encoding='utf-8') as f:
                    config = json.load(f)
                    required_keys = {"genius_key", "use_fallback"}
                    for key in required_keys:
                        if key not in config:
                            config[key] = "" if key == "genius_key" else True
                    return config
            else:
                default_config = {
                    "genius_key": "", 
                    "use_fallback": True,
                    "cache_enabled": True,
                    "max_retries": 3,
                    "timeout": 15,
                    "match_threshold": 25
                }
                save_config(default_config)
                return default_config
        except (json.JSONDecodeError, PermissionError) as e:
            print(f"Error loading config: {e}", type_="ERROR")
            return {
                "genius_key": "", 
                "use_fallback": True, 
                "cache_enabled": True,
                "max_retries": 3,
                "timeout": 15,
                "match_threshold": 25
            }

    def save_config(config: Dict[str, Any]) -> bool:
        try:
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            temp_path = CONFIG_PATH.with_suffix('.tmp')
            with open(temp_path, "w", encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            temp_path.replace(CONFIG_PATH)
            return True
        except Exception as e:
            print(f"Error saving config: {e}", type_="ERROR")
            return False

    def get_config_value(key: str, default: Any = None) -> Any:
        config = load_config()
        return config.get(key, default)

    def set_config_value(key: str, value: Any) -> bool:
        config = load_config()
        if not isinstance(value,str):
            if key == "timeout" and not isinstance(value, (int, float)) or value <= 0:
                print(f"Invalid timeout value: {value}", type_="ERROR")
                return False
            if key == "max_retries" and not isinstance(value, int) or value < 0:
                print(f"Invalid max_retries value: {value}", type_="ERROR")
                return False
            if key == "match_threshold" and not isinstance(value, (int, float)) or not 0 <= value <= 100:
                print(f"Invalid match_threshold value: {value}", type_="ERROR")
                return False
        config[key] = value
        return save_config(config)

    def clean_song_title(title: str) -> str:
        if not title:
            return ""
        title = re.sub(r'\s*\(.*?\)\s*', ' ', title)
        title = re.sub(r'\s*\[.*?\]\s*', ' ', title)
        title = re.sub(r'\s*-\s*(feat|ft|featuring).*', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\s*-\s*remaster.*', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\s*-\s*radio edit.*', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\s+', ' ', title).strip()
        return title

    def calculate_similarity(str1: str, str2: str) -> float:
        if not str1 or not str2:
            return 0.0
        str1 = str1.lower().strip()
        str2 = str2.lower().strip()
        if str1 == str2:
            return 100.0
        if str1 in str2 or str2 in str1:
            shorter = min(len(str1), len(str2))
            longer = max(len(str1), len(str2))
            return min(95.0, (shorter / longer) * 100)
        words1 = set(str1.split())
        words2 = set(str2.split())
        if not words1 or not words2:
            return 0.0
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        jaccard = intersection / union
        partial_matches = 0
        for w1 in words1:
            for w2 in words2:
                if len(w1) >= 3 and len(w2) >= 3:
                    if w1 in w2 or w2 in w1:
                        partial_matches += 1
        partial_score = min(20, partial_matches * 5)
        base_score = jaccard * 70
        return min(100.0, base_score + partial_score)

    def find_best_match(song_title: str, artist_name: str, hits: List[Dict]) -> Tuple[Optional[Dict], float]:
        if not hits:
            return None, 0.0
        clean_title = clean_song_title(song_title)
        clean_artist = artist_name.strip() if artist_name else ""
        best_match = None
        best_score = 0.0
        match_threshold = get_config_value("match_threshold", 25)
        print(f"Searching for: '{clean_title}' by '{clean_artist}'", type_="INFO")

        # --- MODIFIED: only evaluate the first hit that meets threshold ---
        for hit in hits[:10]:
            result = hit.get("result", {})
            genius_title = result.get("title", "")
            genius_artist = result.get("primary_artist", {}).get("name", "")
            clean_genius_title = clean_song_title(genius_title)
            title_score = calculate_similarity(clean_title, clean_genius_title)
            artist_score = calculate_similarity(clean_artist, genius_artist) if clean_artist else 50.0
            combined_score = (title_score * 0.75) + (artist_score * 0.25)
            if combined_score >= match_threshold:
                best_match = result
                best_score = combined_score
                # Log only the best match once
                print(f"Best Match: '{genius_title}' by '{genius_artist}' - Score: {combined_score:.1f}%", type_="INFO")
                break
        return best_match, best_score
lyrics()