"""
Tool definitions for LLM function calling, converted from the simulation API spec.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_houses_by_platform",
            "description": "查询可租房源。district=行政区(海淀/朝阳/大兴等)；area=商圈(望京/国贸/西二旗)；近地铁用max_subway_dist=800；按离地铁从近到远用sort_by=subway_distance,sort_order=asc；bedrooms=卧室数(1,2或2,3)；不传listing_platform默认安居客。",
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
                    "sort_by": {"type": "string", "description": "排序：price(价格)/area(面积)/subway_distance(地铁距离)"},
                    "sort_order": {"type": "string", "description": "asc(升序)或desc(降序)；离地铁从近到远用asc"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_house_by_id",
            "description": "根据房源ID获取详情（面积、楼层、朝向、电梯、地铁距离、通勤）。用户问「这套离地铁多远」「HF_xx的详情」时调用。",
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
            "description": "获取某房源在链家/安居客/58同城各平台的价格。用户问「HF_xx在各平台多少钱」「比较各平台价格」时调用。",
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
            "description": "办理租房。需要house_id和listing_platform。用户说「租这套」「就租第一套」时，用上下文中的房源ID。",
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

SYSTEM_PROMPT = """你是北京租房顾问，用工具查询房源、详情、租房等。

## 工具使用
1. **找房**：get_houses_by_platform。参数映射：
   - 区域：海淀/朝阳/大兴/西城/东城→district；望京/国贸/西二旗→area（商圈）
   - 近地铁/离地铁近→max_subway_dist=800；离地铁500米→max_subway_dist=500
   - 按离地铁从近到远排→sort_by=subway_distance, sort_order=asc
   - 两居/三居→bedrooms="2"或"3"；两居或三居→bedrooms="2,3"
   - 精装/简装→decoration；有电梯→elevator="true"
   - 链家/安居客/58同城→listing_platform；整租/合租→rental_type；民水民电→utilities_type
2. **某套房详情**（面积/楼层/朝向/电梯/地铁距离）：get_house_by_id(house_id)
3. **某套房各平台价格**：get_house_listings(house_id)
4. **附近房源**（西二旗/望京SOHO等）：get_houses_nearby(landmark_id)
5. **租房**：rent_house(house_id, listing_platform)，平台默认安居客
6. **退租**：terminate_rental

## 指代消解（有【上下文】时）
- 「这套」「那套」→用上下文第一个ID
- 「第一套」→第一个；「第二套」→第二个；「第三套」→第三个
- 「便宜那套」「最近那套」→按价格/地铁距离排序后取第一个
- 问详情/价格/租房时，用对应ID调用工具

## 回复要求
- 无结果：必须含「没有」
- 仅一套且用户问还有吗：必须含「没有其他的了，只有这一套」
- 租房成功：以「好的」开头
- 有房源时：每套写清 房源ID、小区、区、户型、面积、月租、装修、朝向、地铁站及距离

## 其他
- 打招呼/闲聊：正常回复，不调用工具
- 用户说「换XX区看看」「大兴区呢」：用新区域重新查，可保留户型预算等条件"""
