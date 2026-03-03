"""
Tool definitions for LLM function calling, converted from the simulation API spec.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_houses_by_platform",
            "description": "查询可租房源，支持按平台、区域、商圈、价格、户型、装修、地铁等多条件筛选。不传listing_platform则默认安居客。",
            "parameters": {
                "type": "object",
                "properties": {
                    "listing_platform": {"type": "string", "enum": ["链家", "安居客", "58同城"], "description": "挂牌平台，不传默认安居客"},
                    "district": {"type": "string", "description": "行政区，逗号分隔，如 海淀,朝阳"},
                    "area": {"type": "string", "description": "商圈，逗号分隔，如 望京,西二旗"},
                    "min_price": {"type": "integer", "description": "最低月租金（元）"},
                    "max_price": {"type": "integer", "description": "最高月租金（元）"},
                    "bedrooms": {"type": "string", "description": "卧室数，逗号分隔，如 1,2"},
                    "rental_type": {"type": "string", "description": "整租 或 合租"},
                    "decoration": {"type": "string", "description": "精装/简装"},
                    "orientation": {"type": "string", "description": "朝向，如 朝南、南北"},
                    "elevator": {"type": "string", "description": "是否有电梯：true/false"},
                    "min_area": {"type": "integer", "description": "最小面积（平米）"},
                    "max_area": {"type": "integer", "description": "最大面积（平米）"},
                    "subway_line": {"type": "string", "description": "地铁线路，如 13号线"},
                    "max_subway_dist": {"type": "integer", "description": "最大地铁距离（米），近地铁建议800"},
                    "subway_station": {"type": "string", "description": "地铁站名，如 车公庄站"},
                    "utilities_type": {"type": "string", "description": "水电类型，如 民水民电"},
                    "available_from_before": {"type": "string", "description": "可入住日期上限，YYYY-MM-DD"},
                    "commute_to_xierqi_max": {"type": "integer", "description": "到西二旗通勤时间上限（分钟）"},
                    "sort_by": {"type": "string", "description": "排序字段：price/area/subway"},
                    "sort_order": {"type": "string", "description": "asc 或 desc"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_house_by_id",
            "description": "根据房源ID获取单套房源详情（面积、楼层、朝向、电梯、地铁距离、通勤等）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "house_id": {"type": "string", "description": "房源ID，如 HF_2001"},
                },
                "required": ["house_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_house_listings",
            "description": "根据房源ID获取该房源在链家/安居客/58同城各平台的全部挂牌记录和价格。",
            "parameters": {
                "type": "object",
                "properties": {
                    "house_id": {"type": "string", "description": "房源ID，如 HF_2001"},
                },
                "required": ["house_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_houses_nearby",
            "description": "以地标（公司/地铁站/商圈）为圆心查附近房源，返回距离信息。",
            "parameters": {
                "type": "object",
                "properties": {
                    "landmark_id": {"type": "string", "description": "地标ID或名称，如 百度、西二旗站、望京SOHO"},
                    "max_distance": {"type": "number", "description": "最大直线距离（米），默认2000"},
                    "listing_platform": {"type": "string", "enum": ["链家", "安居客", "58同城"]},
                },
                "required": ["landmark_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_houses_by_community",
            "description": "按小区名查询可租房源。用于查某小区的房源或隐性属性。",
            "parameters": {
                "type": "object",
                "properties": {
                    "community": {"type": "string", "description": "小区名，如 建清园(南区)"},
                    "listing_platform": {"type": "string", "enum": ["链家", "安居客", "58同城"]},
                },
                "required": ["community"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rent_house",
            "description": "租房：将该房源设为已租。需要房源ID和平台。",
            "parameters": {
                "type": "object",
                "properties": {
                    "house_id": {"type": "string", "description": "房源ID"},
                    "listing_platform": {"type": "string", "enum": ["链家", "安居客", "58同城"], "description": "租赁平台"},
                },
                "required": ["house_id", "listing_platform"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "terminate_rental",
            "description": "退租：将该房源恢复为可租。",
            "parameters": {
                "type": "object",
                "properties": {
                    "house_id": {"type": "string", "description": "房源ID"},
                    "listing_platform": {"type": "string", "enum": ["链家", "安居客", "58同城"]},
                },
                "required": ["house_id", "listing_platform"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_landmarks",
            "description": "获取地标列表（地铁站/公司/商圈），支持按类别和行政区筛选。",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "类别：subway/company/landmark"},
                    "district": {"type": "string", "description": "行政区，如 海淀"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_nearby_landmarks",
            "description": "查询小区周边地标（商超/公园），按距离排序。",
            "parameters": {
                "type": "object",
                "properties": {
                    "community": {"type": "string", "description": "小区名"},
                    "type": {"type": "string", "description": "类型：shopping(商超) 或 park(公园)"},
                },
                "required": ["community"],
            },
        },
    },
]

SYSTEM_PROMPT = """你是北京租房顾问。你可以使用工具查询房源、获取房源详情、租房、退租等。

规则：
1. 用户找房时，调用 get_houses_by_platform 查询，根据用户条件填写参数
2. 用户问某套房详情时，调用 get_house_by_id
3. 用户问某套房各平台价格时，调用 get_house_listings
4. 用户问附近房源时，调用 get_houses_nearby
5. 用户要租房时，调用 rent_house（平台默认安居客）
6. 用户要退租时，调用 terminate_rental
7. 无结果时回复必须包含「没有」二字
8. 仅一套时包含「没有其他的了，只有这一套」
9. 租房成功以「好的」开头
10. 回复包含所有房源ID，每套写清：房源ID、小区、区、户型、面积、月租、装修、朝向、地铁站及距离
11. 用户打招呼/闲聊时正常回复，不调用工具"""
