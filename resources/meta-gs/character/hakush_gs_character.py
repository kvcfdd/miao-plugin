import json
import sys
import os
import re
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

try:
    import requests
except ImportError:
    print("[INFO] requests库未安装，尝试自动安装...")
    import subprocess
    import sys
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-i", "https://pypi.tuna.tsinghua.edu.cn/simple", "requests"])
        import requests
        print("[INFO] requests安装成功。")
    except Exception as e:
        print(f"[INFO] requests自动安装失败: {e}。程序终止。")
        sys.exit(1)

WEAPON_MAP_SRC_CONSTANT_TO_KEY = {
    "WEAPON_SWORD_ONE_HAND": "sword",
    "WEAPON_CATALYST": "catalyst",
    "WEAPON_CLAYMORE": "claymore",
    "WEAPON_BOW": "bow",
    "WEAPON_POLE": "polearm"
}

PARAM_REGEX = re.compile(r"\{param(\d+):([FICP][0-9A-Z]*[DP]?)\}")
LINK_REGEX = re.compile(r"\{LINK.*?(/LINK)?\}")
COLOR_TAG_REGEX = re.compile(r"</?color.*?>")
HTML_TAG_REGEX = re.compile(r"<[^>]+>")

SKILL_ID_SUFFIXES_FROM_ARRAY_IDX = {0: "1", 1: "2", 2: "5"}
DEFAULT_TALENT_CONS = {"a": 0, "e": 3, "q": 5}

def custom_round_half_up(number, precision=2):
    if not isinstance(number, (int, float, Decimal)):
        try:
            number = Decimal(str(number))
        except (InvalidOperation, TypeError, ValueError):
            return str(number)
    if not isinstance(number, Decimal):
         try:
            number = Decimal(str(number))
         except (InvalidOperation, TypeError, ValueError):
            return str(number)

    if precision == 0:
        quantizer = Decimal('1')
    else:
        quantizer = Decimal('1e-' + str(precision))
    
    try:
        rounded_decimal = number.quantize(quantizer, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return str(number) 

    s = str(rounded_decimal)
    if '.' in s:
        s = s.rstrip('0').rstrip('.')
    return s

def custom_format_string_from_rounded(rounded_str_val):
    if '.' in rounded_str_val:
        s = rounded_str_val.rstrip('0').rstrip('.')
        return s
    return rounded_str_val

def format_talent_value_for_display(param_value, fmt_char):
    try:
        val_float = float(param_value)
        if (fmt_char.startswith('F') and fmt_char.endswith('P')) or (fmt_char == 'P'):
            rounded_str = custom_round_half_up(Decimal(str(val_float)) * Decimal('100'), 2)
            return custom_format_string_from_rounded(rounded_str) + "%"
        else:
            rounded_str = custom_round_half_up(Decimal(str(val_float)), 2)
            return custom_format_string_from_rounded(rounded_str)
    except (ValueError, TypeError, InvalidOperation):
        return str(param_value)

def get_numeric_talent_value(param_value, fmt_char):
    try:
        val_decimal = Decimal(str(param_value))
        if (fmt_char.startswith('F') and fmt_char.endswith('P')) or (fmt_char == 'P'):
            val_decimal *= Decimal('100')
        
        s = custom_round_half_up(val_decimal, 2)
        return float(s) if '.' in s else int(s)
    except (ValueError, TypeError, InvalidOperation):
        return 0

def parse_talent_desc_params_for_display(desc_str, params_for_level):
    output_parts = []
    last_idx = 0
    for match in PARAM_REGEX.finditer(desc_str):
        start, end = match.span()
        output_parts.append(desc_str[last_idx:start])
        param_idx = int(match.group(1)) - 1
        fmt_char = match.group(2)
        if 0 <= param_idx < len(params_for_level):
            raw_value = params_for_level[param_idx]
            formatted_val = format_talent_value_for_display(raw_value, fmt_char)
            output_parts.append(formatted_val)
        else:
            output_parts.append(match.group(0))
        last_idx = end
    output_parts.append(desc_str[last_idx:])
    final_str = "".join(output_parts)

    final_str = final_str.replace("+", " + ").replace("/", " / ")

    final_str = re.sub(r'\s\s+', ' ', final_str).strip()
    return final_str

def clean_description_text(text_blob, preserve_html_tags=None):
    if not isinstance(text_blob, str): return []
    text_blob = text_blob.replace("{/LINK}", "")
    def remove_newline_in_i_tag(s):
        def repl(m):
            inner = m.group(1).replace('\\n', '').replace('\n', '')
            return f"<i>{inner}</i>"
        return re.sub(r"<i>(.*?)</i>", repl, s, flags=re.DOTALL)
    text_blob = remove_newline_in_i_tag(text_blob)
    lines = text_blob.split('\\n')
    cleaned_lines = []
    preserve_html_tags = preserve_html_tags or []
    if preserve_html_tags:
        preserve_pattern = re.compile(r'(</?(' + '|'.join(preserve_html_tags) + r')[^>]*>)', re.IGNORECASE)
    else:
        preserve_pattern = None
    full_color_line_pattern = re.compile(r'^\s*<color[^>]*>(.*?)</color>\s*$', re.IGNORECASE | re.DOTALL)
    for line in lines:
        m = full_color_line_pattern.match(line)
        if m:
            inner = m.group(1).strip()
            line = f"<h3>{inner}</h3>"
        else:
            pass

        line = LINK_REGEX.sub("", line)
        tag_placeholders = {}
        if preserve_pattern:
            def _replace_preserve_tag(m):
                placeholder = f"__HTMLTAG_{len(tag_placeholders)}__"
                tag_placeholders[placeholder] = m.group(1)
                return placeholder
            line = preserve_pattern.sub(_replace_preserve_tag, line)
        line = HTML_TAG_REGEX.sub("", line)
        if preserve_pattern:
            for placeholder, tag in tag_placeholders.items():
                line = line.replace(placeholder, tag)
        line = line.strip()
        if line: cleaned_lines.append(line)
    return cleaned_lines

def fetch_character_json_by_id(char_id):
    url = f"https://api.hakush.in/gi/data/zh/character/{char_id}.json"
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        print("处理失败")
        sys.exit(1)

def download_icon(icon_name, save_path):
    url = f"https://api.hakush.in/gi/UI/{icon_name}.webp"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            with open(save_path, "wb") as f:
                f.write(resp.content)
        else:
            print(f"[INFO] 下载失败: {url} 状态码: {resp.status_code}")
    except Exception as e:
        print(f"[INFO] 下载图标异常: {url} 错误: {e}")

def download_all_icons(src, out, talentCons):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    char_folder = os.path.join(script_dir, out['name'])
    icons_folder = os.path.join(char_folder, "icons")
    os.makedirs(icons_folder, exist_ok=True)
    cons = src.get('Constellations', [])
    for idx in range(6):
        if idx < len(cons):
            icon = cons[idx].get('Icon', '')
            if icon:
                save_name = f"cons-{idx+1}.webp"
                save_path = os.path.join(icons_folder, save_name)
                download_icon(icon, save_path)

    passives = src.get('Passives', [])
    for idx, p in enumerate(passives):
        icon = p.get('Icon', '')
        if icon:
            save_name = f"passive-{idx}.webp"
            save_path = os.path.join(icons_folder, save_name)
            download_icon(icon, save_path)

    skills = src.get('Skills', [])
    for k in ['e', 'q']:
        skill_idx_map = {'a': 0, 'e': 1, 'q': 2}
        skill_idx = skill_idx_map.get(k)
        if skill_idx is not None and skill_idx < len(skills):
            icon = ""
            promote_data_for_skill = skills[skill_idx].get('Promote', {})
            if promote_data_for_skill:
                first_promote_key = sorted(promote_data_for_skill.keys(), key=lambda x: int(x) if x.isdigit() else float('inf'))[0]
                first_promote_level_data = promote_data_for_skill.get(first_promote_key)
                if isinstance(first_promote_level_data, dict):
                    icon = first_promote_level_data.get('Icon', '')
            
            if not icon:
                 icon = skills[skill_idx].get('Icon', '')

            if icon:
                save_name = f"talent-{k}.webp"
                save_path = os.path.join(icons_folder, save_name)
                download_icon(icon, save_path)


def download_extra_imgs(src, out):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    char_folder = os.path.join(script_dir, out['name'])
    imgs_folder = os.path.join(char_folder, "imgs")
    os.makedirs(imgs_folder, exist_ok=True)
    namecard_icon = src.get("CharaInfo", {}).get("Namecard", {}).get("Icon", "")
    if namecard_icon:
        save_path = os.path.join(imgs_folder, "card.webp")
        download_icon(namecard_icon, save_path)
    face_icon = src.get("Icon", "")
    if face_icon:
        save_path = os.path.join(imgs_folder, "face.webp")
        download_icon(face_icon, save_path)
        try:
            from PIL import Image
        except ImportError:
            print("[INFO] Pillow库未安装，尝试自动安装...")
            import subprocess
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "-i", "https://pypi.tuna.tsinghua.edu.cn/simple", "Pillow"])
                from PIL import Image
                print("[INFO] Pillow安装成功。")
            except Exception as e:
                print(f"[INFO] Pillow自动安装失败: {e}。无法进行立绘裁剪。")
                return

        m = re.match(r"UI_AvatarIcon_(.+)", face_icon)
        if m:
            tail = m.group(1)
            gacha_icon_name = f"UI_Gacha_AvatarImg_{tail}"
            url = f"https://api.hakush.in/gi/UI/{gacha_icon_name}.webp"
            splash_path = os.path.join(imgs_folder, "splash.webp")
            try:
                resp = requests.get(url, timeout=15)
                if resp.status_code == 200:
                    with open(splash_path, "wb") as f:
                        f.write(resp.content)
                    with Image.open(splash_path) as img:
                        w, h = img.size
                        target_ratio = 7 / 5
                        cur_ratio = w / h
                        if abs(cur_ratio - target_ratio) > 1e-3:
                            if cur_ratio > target_ratio:
                                new_w = int(h * target_ratio)
                                left = (w - new_w) // 2
                                right = left + new_w
                                img_cropped = img.crop((left, 0, right, h))
                            else:
                                new_h = int(w / target_ratio)
                                top = (h - new_h) // 2
                                bottom = top + new_h
                                img_cropped = img.crop((0, top, w, bottom))
                            img_cropped.save(splash_path)
            except Exception as e:
                print(f"[INFO] 下载/裁剪立绘异常: {url} 错误: {e}")

def main(src_path, dst_path_fixed, download_images=False):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    char_id = int(src_path)
    src = fetch_character_json_by_id(src_path)
    char_id_str = str(char_id)
    char_id_last3 = char_id_str[-3:].zfill(3)
    out = {}
    out['id'] = char_id
    out['name'] = src['Name']
    out['abbr'] = src['Name']
    out['title'] = src['CharaInfo']['Title']
    rarity_str = src.get('Rarity', "")
    if rarity_str == "QUALITY_ORANGE": out['star'] = 5
    elif rarity_str == "QUALITY_PURPLE": out['star'] = 4
    else:
        try: out['star'] = int(rarity_str) if rarity_str.isdigit() else 5
        except ValueError: out['star'] = 5
    out['elem'] = src.get('Element', '').lower()
    out['allegiance'] = src['CharaInfo']['Native']
    weapon_type_from_src_weapon_field = src.get('Weapon')
    out['weapon'] = WEAPON_MAP_SRC_CONSTANT_TO_KEY.get(
        weapon_type_from_src_weapon_field,
        weapon_type_from_src_weapon_field.lower().replace('weapon_','') if weapon_type_from_src_weapon_field else "unknown"
    )
    out['birth'] = f"{src['CharaInfo']['Birth'][0]}-{src['CharaInfo']['Birth'][1]}"
    out['astro'] = src['CharaInfo']['Constellation']
    cleaned_top_desc_lines = clean_description_text(src['Desc'])
    out['desc'] = cleaned_top_desc_lines[0] if cleaned_top_desc_lines else src.get('Desc', '')
    out['cncv'] = src['CharaInfo']['VA']['Chinese']
    out['jpcv'] = src['CharaInfo']['VA']['Japanese']
    out['costume'] = bool(src['CharaInfo'].get('Costume', [])) and len(src['CharaInfo']['Costume']) > 1
    out['ver'] = 1
    stats_modifier_src = src.get('CharaInfo', {}).get('StatsModifier', src.get('StatsModifier', {}))
    base_hp_src = src.get('BaseHP', 0)
    base_atk_src = src.get('BaseATK', 0)
    base_def_src = src.get('BaseDEF', 0)
    hp_mod_90_key = None
    if 'HP' in stats_modifier_src:
        if '90' in stats_modifier_src['HP']: hp_mod_90_key = '90'
        elif '90.0' in stats_modifier_src['HP']: hp_mod_90_key = '90.0'
    atk_mod_90_key = None
    if 'ATK' in stats_modifier_src:
        if '90' in stats_modifier_src['ATK']: atk_mod_90_key = '90'
        elif '90.0' in stats_modifier_src['ATK']: atk_mod_90_key = '90.0'
    def_mod_90_key = None
    if 'DEF' in stats_modifier_src:
        if '90' in stats_modifier_src['DEF']: def_mod_90_key = '90'
        elif '90.0' in stats_modifier_src['DEF']: def_mod_90_key = '90.0'
    hp_mod_90 = float(stats_modifier_src.get('HP', {}).get(hp_mod_90_key, 1.0)) if hp_mod_90_key else 1.0
    atk_mod_90 = float(stats_modifier_src.get('ATK', {}).get(atk_mod_90_key, 1.0)) if atk_mod_90_key else 1.0
    def_mod_90 = float(stats_modifier_src.get('DEF', {}).get(def_mod_90_key, 1.0)) if def_mod_90_key else 1.0
    last_ascension_stats = {}
    if 'Ascension' in stats_modifier_src and stats_modifier_src['Ascension'] and isinstance(stats_modifier_src['Ascension'], list):
        last_ascension_stats = stats_modifier_src['Ascension'][-1]
    
    asc_hp_bonus = last_ascension_stats.get('FIGHT_PROP_BASE_HP', 0)
    asc_atk_bonus = last_ascension_stats.get('FIGHT_PROP_BASE_ATTACK', 0)
    asc_def_bonus = last_ascension_stats.get('FIGHT_PROP_BASE_DEFENSE', 0)
    base_attr_hp_raw = base_hp_src * hp_mod_90 + asc_hp_bonus
    base_attr_atk_raw = base_atk_src * atk_mod_90 + asc_atk_bonus
    base_attr_def_raw = base_def_src * def_mod_90 + asc_def_bonus

    def _format_base_attr(val):
        s = custom_round_half_up(val, 2)
        return float(s) if '.' in s else int(s)

    out['baseAttr'] = {
        "hp": _format_base_attr(base_attr_hp_raw),
        "atk": _format_base_attr(base_attr_atk_raw),
        "def": _format_base_attr(base_attr_def_raw),
    }
    for key in ["atk"]:
        val_str = str(out['baseAttr'][key])
        if '.' in val_str and val_str.endswith('.0'):
            out['baseAttr'][key] = int(float(val_str))

    grow_attr_key = "unknown"; grow_attr_value_raw = 0.0
    possible_grow_props = {
        'FIGHT_PROP_CRITICAL': ("cpct", 100),
        'FIGHT_PROP_CRITICAL_HURT': ("cdmg", 100),
        'FIGHT_PROP_HEAL_ADD': ("heal", 100),
        'FIGHT_PROP_CHARGE_EFFICIENCY': ("recharge", 100),
        'FIGHT_PROP_ELEMENT_MASTERY': ("mastery", 1),
        'FIGHT_PROP_HP_PERCENT': ("hpPct", 100),
        'FIGHT_PROP_ATTACK_PERCENT': ("atkPct", 100),
        'FIGHT_PROP_DEFENSE_PERCENT': ("defPct", 100),
        'FIGHT_PROP_PHYSICAL_ADD_HURT': ("phy", 100)
    }
    dmg_add_hurt_pattern = re.compile(r'^FIGHT_PROP_(?!PHYSICAL_)([A-Z_]+)_ADD_HURT$')
    if last_ascension_stats:
        for prop_key_src in last_ascension_stats:
            m = dmg_add_hurt_pattern.match(prop_key_src)
            if m:
                grow_attr_key = "dmg"
                grow_attr_value_raw = last_ascension_stats[prop_key_src] * 100
                break
        else:
            for prop_key_src, (target_key, multiplier) in possible_grow_props.items():
                if prop_key_src in last_ascension_stats:
                    grow_attr_key = target_key
                    grow_attr_value_raw = last_ascension_stats[prop_key_src] * multiplier
                    break
    
    formatted_grow_attr_str = custom_round_half_up(grow_attr_value_raw, 1)
    out['growAttr'] = {
        "key": grow_attr_key,
        "value": float(formatted_grow_attr_str) if '.' in formatted_grow_attr_str else int(formatted_grow_attr_str)
    }
    out['talentId'] = {}
    skill_type_keys = ['a', 'e', 'q']
    for i, skill_key_target_output in enumerate(skill_type_keys):
        if i < len(src.get('Skills', [])):
            suffix = SKILL_ID_SUFFIXES_FROM_ARRAY_IDX.get(i, str(i+1))
            talent_id_str = f"1{char_id_last3}{suffix}"
            out['talentId'][talent_id_str] = skill_key_target_output

    out['talentCons'] = {"a": 0, "e": 0, "q": 0}
    if 'Constellations' in src and src['Constellations']:
        skill_name_to_key = {}
        if src.get('Skills'):
            for i, skill_key in enumerate(skill_type_keys):
                if i < len(src['Skills']):
                    skill_obj = src['Skills'][i]
                    skill_name_to_key[skill_obj.get('Name', '').strip()] = skill_key
        
        cons_map = {2: 3, 4: 5}
        for cons_idx, cons_num in cons_map.items():
            if cons_idx < len(src['Constellations']):
                desc = src['Constellations'][cons_idx].get('Desc', '')
                m = re.search(r'>([^<]+?)的技能等级提高3级', desc)
                if not m:
                    m = re.search(r'(.+?)的技能等级提高3级', desc)
                if m:
                    skill_name = m.group(1).strip()
                    for name, key in skill_name_to_key.items():
                        if skill_name in name or name in skill_name:
                            out['talentCons'][key] = cons_num
                            break

    materials_src = src.get('Materials', {})
    asc_mats_all_tiers = materials_src.get('Ascensions', [])
    talent_mats_src_list_of_lists = materials_src.get('Talents', [])
    def get_mat_name_by_id_or_index(mats_list_for_tier, target_id=None, index=None, default=""):
        if not mats_list_for_tier: return default
        if target_id:
            for mat_item in mats_list_for_tier:
                if mat_item.get("Id") == target_id: return mat_item.get("Name", default)
        if index is not None and 0 <= index < len(mats_list_for_tier) and mats_list_for_tier[index]:
            return mats_list_for_tier[index].get('Name', default)
        return default
    
    highest_normal_enemy_drop = ""
    if asc_mats_all_tiers and isinstance(asc_mats_all_tiers, list) and asc_mats_all_tiers:
        last_asc_tier_mats = asc_mats_all_tiers[-1].get('Mats', [])
        highest_normal_enemy_drop = get_mat_name_by_id_or_index(last_asc_tier_mats, index=3)
        if not highest_normal_enemy_drop:
            highest_normal_enemy_drop = "？？？"
            
    talent_book_name = ""; weekly_boss_mat_name = ""
    if talent_mats_src_list_of_lists and isinstance(talent_mats_src_list_of_lists, list) and \
       talent_mats_src_list_of_lists[0] and isinstance(talent_mats_src_list_of_lists[0], list) and \
       talent_mats_src_list_of_lists[0][-1]: 
        
        last_talent_tier_mats_for_first_skill = talent_mats_src_list_of_lists[0][-1].get('Mats', [])
        if last_talent_tier_mats_for_first_skill:
            talent_book_name = get_mat_name_by_id_or_index(last_talent_tier_mats_for_first_skill, index=0)
            if len(last_talent_tier_mats_for_first_skill) > 2:
                weekly_boss_mat_name = get_mat_name_by_id_or_index(last_talent_tier_mats_for_first_skill, index=2)
                
    out['materials'] = {
        "gem": get_mat_name_by_id_or_index(asc_mats_all_tiers[-1].get('Mats', []), index=0) if asc_mats_all_tiers else "",
        "boss": get_mat_name_by_id_or_index(asc_mats_all_tiers[-1].get('Mats', []), index=1) if asc_mats_all_tiers else "",
        "specialty": get_mat_name_by_id_or_index(asc_mats_all_tiers[-1].get('Mats', []), index=2) if asc_mats_all_tiers else "",
        "normal": highest_normal_enemy_drop, "talent": talent_book_name, "weekly": weekly_boss_mat_name
    }
    
    out['talent'] = {}; talent_data_for_json = {}

    def _format_decimal_to_final_num(dec_val, precision=2):
        s_val = custom_round_half_up(dec_val, precision)
        try:
            if '.' in s_val:
                return float(s_val)
            else:
                return int(s_val)
        except ValueError:
             return s_val


    for src_skill_idx, skill_key_target_output in enumerate(skill_type_keys):
        if src_skill_idx >= len(src.get('Skills', [])): continue
        src_skill_obj = src['Skills'][src_skill_idx]
        
        current_talent_id_str_numeric_part = ""
        for tid_str_map, tkey_map_val in out['talentId'].items():
            if tkey_map_val == skill_key_target_output: current_talent_id_str_numeric_part = tid_str_map; break
        
        skill_desc_lines = clean_description_text(src_skill_obj['Desc'], preserve_html_tags=['h3', 'i'])
        skill_output_dict = {
            "id": int(current_talent_id_str_numeric_part) if current_talent_id_str_numeric_part and current_talent_id_str_numeric_part.isdigit() else current_talent_id_str_numeric_part,
            "name": src_skill_obj['Name'], "desc": skill_desc_lines, "tables": []
        }
        current_skill_talent_data_numeric_dict = {}

        if 'Promote' in src_skill_obj and src_skill_obj['Promote']:
            base_level_promote_data = None
            sorted_promote_keys = sorted(src_skill_obj['Promote'].keys(), key=lambda x: int(x) if x.isdigit() else float('inf'))
            if sorted_promote_keys:
                first_valid_key = next((key for key in sorted_promote_keys if src_skill_obj['Promote'][key] is not None), None)
                if first_valid_key: base_level_promote_data = src_skill_obj['Promote'][first_valid_key]

            if base_level_promote_data and 'Desc' in base_level_promote_data:
                desc_templates_from_base = base_level_promote_data['Desc']
                if not isinstance(desc_templates_from_base, list): desc_templates_from_base = [str(desc_templates_from_base)]

                for desc_template_idx, desc_template_full_str in enumerate(desc_templates_from_base):
                    if not desc_template_full_str or '|' not in desc_template_full_str: continue
                    table_name_raw, desc_format_str_template_part = desc_template_full_str.split('|', 1)
                    table_name_clean = table_name_raw.strip()
                    if not table_name_clean: continue
                    
                    unit_keywords = ["生命值上限", "防御力"]; unit = ""
                    for kw in unit_keywords:
                        if any(kw in v for v in [desc_format_str_template_part]): unit = kw; break
                    
                    display_values_for_table_list = []
                    numeric_values_for_main_key_list = []
                    numeric_values_for_components_key_list = []
                    is_sum_format_overall_for_this_table = False
                    is_mul_format_overall_for_this_table = False

                    params_info_from_template_list = []
                    for match_obj in PARAM_REGEX.finditer(desc_format_str_template_part):
                        params_info_from_template_list.append( (int(match_obj.group(1)) - 1, match_obj.group(2)) )

                    max_talent_level_target = 15
                    for level_idx_promote_0_based in range(max_talent_level_target):
                        level_promote_key_in_src = str(level_idx_promote_0_based)
                        current_level_promote_data = src_skill_obj['Promote'].get(level_promote_key_in_src, {})
                        params_for_current_level_list = current_level_promote_data.get('Param', []) if isinstance(current_level_promote_data, dict) else []

                        formatted_str_for_display_value = parse_talent_desc_params_for_display(desc_format_str_template_part, params_for_current_level_list)
                        if unit: formatted_str_for_display_value = formatted_str_for_display_value.replace(unit, '').rstrip()
                        display_values_for_table_list.append(formatted_str_for_display_value)

                        calc_str_no_percent = formatted_str_for_display_value.replace('%', '')
                        eval_str = "".join(calc_str_no_percent.split())

                        current_level_main_numeric_val = 0
                        current_level_components_list = None

                        try:
                            if not eval_str: raise ValueError("Empty string for talent value calculation")

                            if '+' in eval_str:
                                sum_terms_str_list = eval_str.split('+')
                                numeric_sum_terms_decimal = []
                                for term_str_raw in sum_terms_str_list:
                                    term_str = term_str_raw.strip()
                                    if not term_str: raise ValueError(f"Empty term after splitting by '+': {eval_str}")
                                    prod_factors_str_list = term_str.split('*')
                                    current_term_val_decimal = Decimal('1.0')
                                    if len(prod_factors_str_list) > 1:
                                        for factor_str_raw in prod_factors_str_list:
                                            factor_str = factor_str_raw.strip()
                                            if not factor_str: raise ValueError(f"Empty factor after splitting by '*': {term_str}")
                                            current_term_val_decimal *= Decimal(factor_str)
                                    else:
                                        current_term_val_decimal = Decimal(prod_factors_str_list[0])
                                    numeric_sum_terms_decimal.append(current_term_val_decimal)
                                total_sum_decimal = sum(numeric_sum_terms_decimal)
                                current_level_main_numeric_val = _format_decimal_to_final_num(total_sum_decimal)
                                if len(sum_terms_str_list) > 1:
                                    if not is_sum_format_overall_for_this_table:
                                        is_sum_format_overall_for_this_table = True
                                    current_level_components_list = [_format_decimal_to_final_num(d_val) for d_val in numeric_sum_terms_decimal]
                            elif '*' in eval_str:
                                mul_terms_str_list = eval_str.split('*')
                                numeric_mul_terms_decimal = []
                                for factor_str_raw in mul_terms_str_list:
                                    factor_str = factor_str_raw.strip()
                                    if not factor_str: raise ValueError(f"Empty factor after splitting by '*': {eval_str}")
                                    numeric_mul_terms_decimal.append(Decimal(factor_str))
                                total_mul_decimal = Decimal('1.0')
                                for d_val in numeric_mul_terms_decimal:
                                    total_mul_decimal *= d_val
                                current_level_main_numeric_val = _format_decimal_to_final_num(total_mul_decimal)
                                if len(mul_terms_str_list) > 1:
                                    if not is_mul_format_overall_for_this_table:
                                        is_mul_format_overall_for_this_table = True
                                    current_level_components_list = [_format_decimal_to_final_num(d_val) for d_val in numeric_mul_terms_decimal]
                            else:
                                current_level_main_numeric_val = _format_decimal_to_final_num(Decimal(eval_str))
                                current_level_components_list = None

                        except (ValueError, TypeError, InvalidOperation) as e:
                            temp_raw_numeric_params = []
                            valid_params_for_fallback = True
                            if params_info_from_template_list:
                                if params_for_current_level_list:
                                    for p_idx, fmt_char in params_info_from_template_list:
                                        if p_idx < len(params_for_current_level_list):
                                            raw_param_val = params_for_current_level_list[p_idx]
                                            temp_raw_numeric_params.append(get_numeric_talent_value(raw_param_val, fmt_char))
                                        else: valid_params_for_fallback = False; break
                                else: valid_params_for_fallback = False

                            if not valid_params_for_fallback or not temp_raw_numeric_params:
                                current_level_main_numeric_val = 0
                            elif len(temp_raw_numeric_params) == 1:
                                current_level_main_numeric_val = temp_raw_numeric_params[0]
                            else:
                                current_level_main_numeric_val = temp_raw_numeric_params 
                            current_level_components_list = None

                        numeric_values_for_main_key_list.append(current_level_main_numeric_val)
                        if current_level_components_list is not None:
                            numeric_values_for_components_key_list.append(current_level_components_list)
                        elif is_sum_format_overall_for_this_table or is_mul_format_overall_for_this_table:
                            numeric_values_for_components_key_list.append([])

                    contains_percent = any('%' in str(x) for x in display_values_for_table_list)
                    is_same_val_for_display_table = False
                    if not contains_percent and display_values_for_table_list:
                        is_same_val_for_display_table = all(x == display_values_for_table_list[0] for x in display_values_for_table_list)

                    skill_output_dict['tables'].append({
                        "name": table_name_clean, "unit": unit,
                        "isSame": is_same_val_for_display_table, "values": display_values_for_table_list
                    })

                    if not is_same_val_for_display_table:
                        if numeric_values_for_main_key_list:
                            current_skill_talent_data_numeric_dict[table_name_clean] = numeric_values_for_main_key_list
                        if (is_sum_format_overall_for_this_table or is_mul_format_overall_for_this_table) and numeric_values_for_components_key_list and \
                           any(comp_list for comp_list in numeric_values_for_components_key_list):
                            current_skill_talent_data_numeric_dict[table_name_clean + "2"] = numeric_values_for_components_key_list
        
        if current_skill_talent_data_numeric_dict:
            talent_data_for_json[skill_key_target_output] = current_skill_talent_data_numeric_dict
        out['talent'][skill_key_target_output] = skill_output_dict
    
    out['talentData'] = talent_data_for_json

    out['cons'] = {}
    if 'Constellations' in src and src['Constellations']:
        for idx, con_data_obj in enumerate(src['Constellations']):
            out['cons'][str(idx + 1)] = { "name": con_data_obj['Name'], "desc": clean_description_text(con_data_obj['Desc']) }
    
    out['passive'] = []
    if 'Passives' in src and src['Passives']:
        for passive_data_obj in src['Passives']:
            out['passive'].append({ "name": passive_data_obj['Name'], "desc": clean_description_text(passive_data_obj['Desc']) })
    
    out['attr'] = {"keys": ["hpBase", "atkBase", "defBase", out['growAttr']['key']]}
    out['attr']['details'] = {}
    attr_levels_map_standard = {
        "1": ("1", None), "20": ("20", None), "40": ("40", 0),
        "50": ("50", 1), "60": ("60", 2), "70": ("70", 3),
        "80": ("80", 4), "90": ("90", 5)
    }
    attr_levels_map_breakthrough = {
        "20+": ("20", 0), "40+": ("40", 1), "50+": ("50", 2),
        "60+": ("60", 3), "70+": ("70", 4), "80+": ("80", 5)
    }
    ordered_standard_keys = ["1", "20", "40", "50", "60", "70", "80", "90"]
    ordered_breakthrough_keys = ["20+", "40+", "50+", "60+", "70+", "80+"]

    asc_data_list_from_src = []
    if isinstance(stats_modifier_src.get('Ascension'), list):
        asc_data_list_from_src = stats_modifier_src.get('Ascension', [])
    elif isinstance(stats_modifier_src.get('Ascension'), dict):
        temp_asc_dict = stats_modifier_src.get('Ascension', {})
        sorted_keys = sorted([k for k in temp_asc_dict.keys() if k.isdigit()], key=int)
        asc_data_list_from_src = [temp_asc_dict[k] for k in sorted_keys if k in temp_asc_dict]


    breakthrough_grow_map = {}
    breakthrough_attr_details = {}
    for display_lvl_key in ordered_breakthrough_keys:
        if display_lvl_key not in attr_levels_map_breakthrough: continue
        mult_lvl_key_str_base, asc_idx_for_bonuses_nullable = attr_levels_map_breakthrough[display_lvl_key]
        actual_mult_lvl_key_for_stat = mult_lvl_key_str_base
        if 'HP' in stats_modifier_src and \
           mult_lvl_key_str_base not in stats_modifier_src['HP'] and \
           f"{mult_lvl_key_str_base}.0" in stats_modifier_src['HP']:
            actual_mult_lvl_key_for_stat = f"{mult_lvl_key_str_base}.0"
        
        hp_curve = float(stats_modifier_src.get('HP', {}).get(actual_mult_lvl_key_for_stat, 1.0))
        atk_curve = float(stats_modifier_src.get('ATK', {}).get(actual_mult_lvl_key_for_stat, 1.0))
        def_curve = float(stats_modifier_src.get('DEF', {}).get(actual_mult_lvl_key_for_stat, 1.0))
        
        hp_bonus_from_ascension, atk_bonus_from_ascension, def_bonus_from_ascension = 0, 0, 0
        current_asc_data_for_bonuses = {}
        if asc_idx_for_bonuses_nullable is not None and 0 <= asc_idx_for_bonuses_nullable < len(asc_data_list_from_src):
            current_asc_data_for_bonuses = asc_data_list_from_src[asc_idx_for_bonuses_nullable]
            if isinstance(current_asc_data_for_bonuses, dict):
                hp_bonus_from_ascension = current_asc_data_for_bonuses.get('FIGHT_PROP_BASE_HP', 0)
                atk_bonus_from_ascension = current_asc_data_for_bonuses.get('FIGHT_PROP_BASE_ATTACK', 0)
                def_bonus_from_ascension = current_asc_data_for_bonuses.get('FIGHT_PROP_BASE_DEFENSE', 0)
        
        grow_stat_val_for_level_raw = 0.0
        if isinstance(current_asc_data_for_bonuses, dict) and current_asc_data_for_bonuses:
            grow_key_target = out['growAttr']['key']
            found_grow = False
            for prop_key_src_check in current_asc_data_for_bonuses:
                m = dmg_add_hurt_pattern.match(prop_key_src_check)
                if m and grow_key_target == "dmg":
                    grow_stat_val_for_level_raw = current_asc_data_for_bonuses[prop_key_src_check] * 100
                    found_grow = True
                    break
            if not found_grow:
                for prop_key_src_check, (target_key_check, multiplier_check) in possible_grow_props.items():
                    if target_key_check == grow_key_target and prop_key_src_check in current_asc_data_for_bonuses:
                        grow_stat_val_for_level_raw = current_asc_data_for_bonuses[prop_key_src_check] * multiplier_check
                        break
        
        formatted_grow_stat_details_str = custom_round_half_up(grow_stat_val_for_level_raw, 2)
        grow_stat_val_final_for_level = float(formatted_grow_stat_details_str) if '.' in formatted_grow_stat_details_str else int(formatted_grow_stat_details_str)
        
        final_hp = base_hp_src * hp_curve + hp_bonus_from_ascension
        final_atk = base_atk_src * atk_curve + atk_bonus_from_ascension
        final_def = base_def_src * def_curve + def_bonus_from_ascension
        
        hp_val = custom_round_half_up(final_hp, 2) 
        atk_val = custom_round_half_up(final_atk, 2)
        def_val = custom_round_half_up(final_def, 2)
        grow_val = custom_round_half_up(grow_stat_val_final_for_level, 2) 
        
        current_level_attr_list = [
            float(hp_val) if '.' in hp_val else int(hp_val),
            float(atk_val) if '.' in atk_val else int(atk_val),
            float(def_val) if '.' in def_val else int(def_val),
            float(grow_val) if '.' in grow_val else int(grow_val)
        ]
        breakthrough_attr_details[display_lvl_key] = current_level_attr_list
        breakthrough_grow_map[display_lvl_key] = current_level_attr_list

    standard_attr_details = {}
    for display_lvl_key in ordered_standard_keys:
        if display_lvl_key not in attr_levels_map_standard: continue
        mult_lvl_key_str_base, asc_idx_for_bonuses_nullable = attr_levels_map_standard[display_lvl_key]
        actual_mult_lvl_key_for_stat = mult_lvl_key_str_base
        if 'HP' in stats_modifier_src and \
           mult_lvl_key_str_base not in stats_modifier_src['HP'] and \
           f"{mult_lvl_key_str_base}.0" in stats_modifier_src['HP']:
             actual_mult_lvl_key_for_stat = f"{mult_lvl_key_str_base}.0"

        hp_curve = float(stats_modifier_src.get('HP', {}).get(actual_mult_lvl_key_for_stat, 1.0))
        atk_curve = float(stats_modifier_src.get('ATK', {}).get(actual_mult_lvl_key_for_stat, 1.0))
        def_curve = float(stats_modifier_src.get('DEF', {}).get(actual_mult_lvl_key_for_stat, 1.0))
        
        hp_bonus_from_ascension, atk_bonus_from_ascension, def_bonus_from_ascension = 0, 0, 0
        grow_stat_val_final_for_level = 0.0

        current_asc_data_for_bonuses = {}
        if asc_idx_for_bonuses_nullable is not None and 0 <= asc_idx_for_bonuses_nullable < len(asc_data_list_from_src):
            current_asc_data_for_bonuses = asc_data_list_from_src[asc_idx_for_bonuses_nullable]
            if isinstance(current_asc_data_for_bonuses, dict):
                if display_lvl_key == "90":
                     hp_bonus_from_ascension = current_asc_data_for_bonuses.get('FIGHT_PROP_BASE_HP', 0)
                     atk_bonus_from_ascension = current_asc_data_for_bonuses.get('FIGHT_PROP_BASE_ATTACK', 0)
                     def_bonus_from_ascension = current_asc_data_for_bonuses.get('FIGHT_PROP_BASE_DEFENSE', 0)
                else:
                     hp_bonus_from_ascension = current_asc_data_for_bonuses.get('FIGHT_PROP_BASE_HP', 0)
                     atk_bonus_from_ascension = current_asc_data_for_bonuses.get('FIGHT_PROP_BASE_ATTACK', 0)
                     def_bonus_from_ascension = current_asc_data_for_bonuses.get('FIGHT_PROP_BASE_DEFENSE', 0)
        
        grow_stat_val_for_level_raw = 0.0
        if isinstance(current_asc_data_for_bonuses, dict) and current_asc_data_for_bonuses and display_lvl_key == "90":
            grow_key_target = out['growAttr']['key']
            found_grow = False
            for prop_key_src_check in current_asc_data_for_bonuses:
                m = dmg_add_hurt_pattern.match(prop_key_src_check)
                if m and grow_key_target == "dmg":
                    grow_stat_val_for_level_raw = current_asc_data_for_bonuses[prop_key_src_check] * 100
                    found_grow = True; break
            if not found_grow:
                for prop_key_src_check, (target_key_check, multiplier_check) in possible_grow_props.items():
                    if target_key_check == grow_key_target and prop_key_src_check in current_asc_data_for_bonuses:
                        grow_stat_val_for_level_raw = current_asc_data_for_bonuses[prop_key_src_check] * multiplier_check
                        break
            formatted_g_str = custom_round_half_up(grow_stat_val_for_level_raw, 2)
            grow_stat_val_final_for_level = float(formatted_g_str) if '.' in formatted_g_str else int(formatted_g_str)

        if display_lvl_key == "1":
            final_hp = base_hp_src
            final_atk = base_atk_src
            final_def = base_def_src
            grow_stat_val_final_for_level = 0
        else:
            final_hp = base_hp_src * hp_curve + hp_bonus_from_ascension
            final_atk = base_atk_src * atk_curve + atk_bonus_from_ascension
            final_def = base_def_src * def_curve + def_bonus_from_ascension

        hp_val_str = custom_round_half_up(final_hp, 2)
        atk_val_str = custom_round_half_up(final_atk, 2)
        def_val_str = custom_round_half_up(final_def, 2)
        
        current_grow_val_to_use_str = "0"
        if display_lvl_key == "1":
            current_grow_val_to_use_str = "0"
        elif display_lvl_key == "20": 
            current_grow_val_to_use_str = "0"
        elif display_lvl_key == "90":
            current_grow_val_to_use_str = custom_round_half_up(grow_stat_val_final_for_level, 2)
        else: 
            prev_break_key_map = {"40":"20+", "50":"40+", "60":"50+", "70":"60+", "80":"70+"}
            prev_break_key = prev_break_key_map.get(display_lvl_key)
            if prev_break_key in breakthrough_grow_map:
                current_grow_val_to_use_str = custom_round_half_up(breakthrough_grow_map[prev_break_key][3], 2)
            else:
                current_grow_val_to_use_str = "0"


        standard_attr_details[display_lvl_key] = [
            float(hp_val_str) if '.' in hp_val_str else int(hp_val_str),
            float(atk_val_str) if '.' in atk_val_str else int(atk_val_str),
            float(def_val_str) if '.' in def_val_str else int(def_val_str),
            float(current_grow_val_to_use_str) if '.' in current_grow_val_to_use_str else int(current_grow_val_to_use_str)
        ]
    
    for k in ordered_standard_keys:
        if k in standard_attr_details:
            out['attr']['details'][k] = standard_attr_details[k]
    for k in ordered_breakthrough_keys:
        if k in breakthrough_attr_details:
            out['attr']['details'][k] = breakthrough_attr_details[k]

    char_folder = os.path.join(script_dir, out['name'])
    if not os.path.exists(char_folder):
        os.makedirs(char_folder, exist_ok=True)

    if download_images:
        print(f"[INFO] 开始为角色 {out['name']} 下载图片...")
        download_all_icons(src, out, out['talentCons'])
        download_extra_imgs(src, out)
        print(f"[INFO] 角色 {out['name']} 图片下载完成。")

    dst_path_fixed = os.path.join(char_folder, os.path.basename(dst_path_fixed))
    with open(dst_path_fixed, 'w', encoding='utf-8') as f:
        def final_json_serializer(obj):
            if isinstance(obj, Decimal):
                return _format_decimal_to_final_num(obj)
            if isinstance(obj, float):
                return _format_decimal_to_final_num(Decimal(str(obj)))
            elif isinstance(obj, list):
                return [final_json_serializer(x) for x in obj]
            elif isinstance(obj, dict):
                return {k: final_json_serializer(v) for k, v in obj.items()}
            else:
                return obj
        json.dump(final_json_serializer(out), f, ensure_ascii=False, indent=2)
    print(f"成功：{out['name']}")

if __name__ == '__main__':
    script_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        resp = requests.get("https://api.hakush.in/gi/new.json", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        char_ids = data.get("character", [])
        if not char_ids:
            print("处理失败")
            sys.exit(1)
    except Exception:
        print("处理失败")
        sys.exit(1)
    target_output_filename = 'data.json'
    summary_file_path = os.path.join(script_dir, "data.json")
    alias_file_path = os.path.join(script_dir, "alias.js")
    existing_summary_data = {}
    if os.path.exists(summary_file_path):
        try:
            with open(summary_file_path, 'r', encoding='utf-8') as f_sum_read:
                existing_summary_data = json.load(f_sum_read)
            if not isinstance(existing_summary_data, dict):
                existing_summary_data = {}
        except json.JSONDecodeError:
            existing_summary_data = {}
    alias_dict = {}
    if os.path.exists(alias_file_path):
        try:
            with open(alias_file_path, 'r', encoding='utf-8') as f_alias:
                content = f_alias.read()
                m = re.search(r'const\s+alias\s*=\s*\{([\s\S]*?)\};', content)
                if m:
                    body = m.group(1)
                    for line in body.splitlines():
                        line = line.strip().rstrip(',')
                        if not line or ':' not in line: continue
                        k, v = line.split(':', 1)
                        k = k.strip().strip("'\"")
                        alias_dict[k] = v.strip().strip("'\",")
        except Exception:
            pass
    for char_id in char_ids:
        try:
            char_name = None
            char_folder = None
            if str(char_id) in existing_summary_data:
                char_name = existing_summary_data[str(char_id)].get("name")
            if not char_name:
                for item in os.listdir(script_dir):
                    item_path = os.path.join(script_dir, item)
                    if os.path.isdir(item_path):
                        potential_data_file = os.path.join(item_path, target_output_filename)
                        if os.path.exists(potential_data_file):
                            try:
                                with open(potential_data_file, 'r', encoding='utf-8') as f_check:
                                    check_data = json.load(f_check)
                                    if str(check_data.get("id")) == str(char_id):
                                        char_name = check_data.get("name")
                                        break
                            except Exception:
                                continue
            if char_name:
                char_folder = os.path.join(script_dir, char_name)
            else:
                char_folder = None
            need_download_images = True
            if char_name and os.path.isdir(char_folder):
                need_download_images = False
            main(char_id, target_output_filename, download_images=need_download_images)
            if not char_name:
                for item in os.listdir(script_dir):
                    item_path = os.path.join(script_dir, item)
                    if os.path.isdir(item_path):
                        potential_data_file = os.path.join(item_path, target_output_filename)
                        if os.path.exists(potential_data_file):
                            try:
                                with open(potential_data_file, 'r', encoding='utf-8') as f_check:
                                    check_data = json.load(f_check)
                                    if str(check_data.get("id")) == str(char_id):
                                        char_name = check_data.get("name")
                                        break
                            except Exception:
                                continue
            char_data_path = os.path.join(script_dir, char_name, target_output_filename)
            if os.path.exists(char_data_path):
                with open(char_data_path, 'r', encoding='utf-8') as f:
                    full_data = json.load(f)
                simple_data_entry = {
                    "id": full_data["id"],
                    "name": full_data.get("name", "未知角色"),
                    "abbr": full_data.get("abbr", full_data.get("name", "未知角色")),
                    "star": full_data.get("star", 0),
                    "elem": full_data.get("elem", "unknown"),
                    "weapon": full_data.get("weapon", "unknown"),
                    "talentId": full_data.get("talentId", {}),
                    "talentCons": full_data.get("talentCons", DEFAULT_TALENT_CONS.copy())
                }
                if str(full_data["id"]) not in existing_summary_data:
                    existing_summary_data[str(full_data["id"])] = simple_data_entry
                    existing_summary_data = dict(sorted(existing_summary_data.items(), key=lambda x: int(x[0])))
            # alias.js 处理省略日志
            if char_name:
                alias_exists = False
                if os.path.exists(alias_file_path):
                    with open(alias_file_path, 'r', encoding='utf-8') as f_alias:
                        alias_content = f_alias.read()
                    alias_exists = any(
                        line.strip().startswith(f"{char_name}:") or
                        line.strip().startswith(f"'{char_name}':") or
                        line.strip().startswith(f'"{char_name}":')
                        for line in alias_content.splitlines()
                    )
                if not alias_exists:
                    try:
                        if os.path.exists(alias_file_path):
                            idx = alias_content.rfind('}')
                            if idx != -1:
                                insert_line = f"  '{char_name}': '',\n"
                                new_content = alias_content[:idx].rstrip()
                                if not new_content.endswith(','):
                                    new_content += ','
                                new_content += '\n' + insert_line + alias_content[idx:]
                            else:
                                new_content = alias_content + f"\n'{char_name}': '',\n"
                            with open(alias_file_path, 'w', encoding='utf-8') as f_alias:
                                f_alias.write(new_content)
                        else:
                            with open(alias_file_path, 'w', encoding='utf-8') as f_alias:
                                f_alias.write(f"export const alias = {{\n  '{char_name}': '',\n}};\n")
                    except Exception:
                        pass
        except Exception:
            print("处理失败")
    with open(summary_file_path, "w", encoding="utf-8") as f_sum_write:
        json.dump(existing_summary_data, f_sum_write, ensure_ascii=False, indent=2)