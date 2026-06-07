from __future__ import annotations

import random
import zlib
from dataclasses import dataclass, field
from typing import Optional, Dict

from src.utils.df import game_configs, get_str, get_int
from src.classes.effect import load_effect_from_str
from src.systems.cultivation import Realm
from src.classes.weapon_type import WeaponType
from src.classes.items.item import Item


@dataclass
class Weapon(Item):
    """
    兵器类：用于战斗的装备
    字段与 static/game_configs/weapon.csv 对应：
    - weapon_type: 兵器类型（剑、刀、枪等）
    - realm: 装备等级（练气/筑基/金丹/元婴）
    - effects: 解析为 dict，用于与 Avatar.effects 合并
    """
    id: int
    name: str
    weapon_type: WeaponType
    realm: Realm
    desc: str
    effects: dict[str, object] = field(default_factory=dict)
    effect_desc: str = ""
    # 特殊属性（如万魂幡的吞噬魂魄计数）
    special_data: dict = field(default_factory=dict)

    def __hash__(self):
        return hash(self.id)

    def get_info(self, detailed: bool = False) -> str:
        """获取信息"""
        if detailed:
            return self.get_detailed_info()
        return f"{self.name}"

    def get_detailed_info(self) -> str:
        """获取详细信息"""
        from src.i18n import t
        effect_part = t(" Effect: {effect_desc}", effect_desc=self.effect_desc) if self.effect_desc else ""
        return f"[{self.id}] " + t("{name} ({type}·{realm}, {desc}){effect}",
                 name=self.name, type=str(self.weapon_type), realm=str(self.realm), 
                 desc=self.desc, effect=effect_part)
    
    def get_colored_info(self) -> str:
        """获取带颜色标记的信息，供前端渲染使用"""
        r, g, b = self.realm.color_rgb
        return f"<color:{r},{g},{b}>{self.get_info()}</color>"

    def get_structured_info(self) -> dict:
        return {
            "id": str(self.id),
            "name": self.name,
            "desc": self.desc,
            "grade": str(self.realm),
            "realm": str(self.realm),
            "color": self.realm.color_rgb,
            "type": self.weapon_type.value,
            "effect_desc": self.effect_desc,
        }


def _load_weapons_data() -> tuple[Dict[int, Weapon], Dict[str, Weapon]]:
    """从配表加载 weapon 数据。
    返回：新的 (按ID、按名称 的映射)。
    """
    new_by_id: Dict[int, Weapon] = {}
    new_by_name: Dict[str, Weapon] = {}

    df = game_configs.get("weapon")
    if df is None:
        return new_by_id, new_by_name

    for row in df:
        effects = load_effect_from_str(get_str(row, "effects"))
        from src.classes.effect import format_effects_to_text
        effect_desc = format_effects_to_text(effects)

        # 解析weapon_type
        weapon_type_str = get_str(row, "weapon_type")
        weapon_type = WeaponType.from_str(weapon_type_str)
        
        # 解析grade
        grade_str = get_str(row, "grade", "QI_REFINEMENT")
        realm = Realm.from_str(grade_str)

        w = Weapon(
            id=get_int(row, "item_id"),
            name=get_str(row, "name"),
            weapon_type=weapon_type,
            realm=realm,
            desc=get_str(row, "desc"),
            effects=effects,
            effect_desc=effect_desc,
        )

        new_by_id[w.id] = w
        new_by_name[w.name] = w
        
        # 注册到全局注册表 (注意：ItemRegistry 在外部 reset 之后，这里会重新注册)
        from src.classes.items.registry import ItemRegistry
        ItemRegistry.register(w.id, w)

    return new_by_id, new_by_name

# 全局容器
weapons_by_id: Dict[int, Weapon] = {}
weapons_by_name: Dict[str, Weapon] = {}

def reload():
    """重新加载数据，保留全局字典引用"""
    new_id, new_name = _load_weapons_data()
    
    weapons_by_id.clear()
    weapons_by_id.update(new_id)
    
    weapons_by_name.clear()
    weapons_by_name.update(new_name)

# 模块初始化时执行一次
reload()


def _scenario_weapon_id(raw_id: object) -> int:
    try:
        return int(raw_id)
    except (TypeError, ValueError):
        return 960001 + (zlib.crc32(str(raw_id).encode("utf-8")) % 50000)


def _effect_dsl_from_preset(value: object) -> str:
    if isinstance(value, list):
        return ",".join(str(item) for item in value if str(item))
    return str(value or "")


def _weapon_from_preset_item(item: dict[str, object]) -> Weapon:
    raw_id = item.get("id")
    weapon_id = _scenario_weapon_id(raw_id)
    if weapon_id in weapons_by_id:
        return weapons_by_id[weapon_id]

    attributes = item.get("attributes")
    if isinstance(attributes, list) and attributes:
        weapon_type_raw = str(attributes[0])
    else:
        weapon_type_raw = str(item.get("weapon_type") or "SWORD")
    effects = load_effect_from_str(_effect_dsl_from_preset(item.get("effects")))
    if not isinstance(effects, dict):
        effects = {}
    from src.classes.effect import format_effects_to_text
    from src.classes.items.registry import ItemRegistry

    weapon = Weapon(
        id=weapon_id,
        name=str(item.get("name") or raw_id or weapon_id),
        weapon_type=WeaponType.from_str(weapon_type_raw),
        realm=Realm.from_str(str(item.get("required_realm") or item.get("realm") or "QI_REFINEMENT")),
        desc=str(item.get("description") or item.get("desc") or ""),
        effects=effects,
        effect_desc=format_effects_to_text(effects),
    )
    weapons_by_id[weapon.id] = weapon
    weapons_by_name[weapon.name] = weapon
    ItemRegistry.register(weapon.id, weapon)
    return weapon


def _resolved_weapon_candidates() -> list[Weapon]:
    from src.scenario.source_resolver import resolve_source

    data = resolve_source("weapons").data
    raw_items = data.get("weapons")
    if isinstance(raw_items, dict):
        raw_items = [{"id": key, **value} if isinstance(value, dict) else {"id": key} for key, value in raw_items.items()]
    if isinstance(raw_items, list) and raw_items:
        return [_weapon_from_preset_item(dict(item)) for item in raw_items if isinstance(item, dict)]
    return list(weapons_by_id.values())


def get_random_weapon_by_realm(realm: Realm, weapon_type: Optional[WeaponType] = None) -> Optional[Weapon]:
    """获取指定境界（及可选类型）的随机兵器"""
    candidates = [w for w in _resolved_weapon_candidates() if w.realm == realm]
    if weapon_type is not None:
        candidates = [w for w in candidates if w.weapon_type == weapon_type]
        
    if not candidates:
        return None
    return random.choice(candidates).instantiate()
