# -*- coding: utf-8 -*-
"""
地图名汉化
==================================================
fyscs/cs2 仓库的 translations/ 只翻译游戏内文本，不提供地图显示名，
所以这里采用三层方案：

  1. MAP_NAMES  精选整名（知名系列/热门图，人工校对）
  2. WORDS      词根词典（按 _ . 切词逐词翻译，未知词保留原文）
  3. data/mapnames.json  用户自定义覆盖（优先级最高）

cn("ze_backrooms_insomnia") -> "后室2：失眠症"
cn("ze_surf_facility_v2_3") -> "冲浪 设施"
返回 None 表示翻译不出（调用方回退显示原名）。
"""
import io
import json
import os
import re
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USER_FILE = os.path.join(BASE_DIR, "data", "mapnames.json")
PLATFORM_FILE = os.path.join(BASE_DIR, "data", "platform_mapnames.json")
# 云端热更表：由主程序后台从服务器拉取后落到这里（见 fys_reward_app 的
# mapnames_tick）。好处是**补译名不用重新发版** —— 服务器换一份即可。
# 优先级：用户自定义 > 云端表 > 平台表 > 内置精选 > 词根合成。
REMOTE_FILE = os.path.join(BASE_DIR, "data", "mapnames_remote.json")
# EXG 图池补充图的中文名：由 _exg_merge.py 从 EXG 公开表抓下来（随包内置）。
# 这批图不在官方地图库里，平台表没有它们；放在「精选整名」之后、词根合成之前，
# 纯粹是兜住「官方没译名、词根又拼不出」的那批（否则界面显示 "1 schizo" 这种）。
EXG_FILE = os.path.join(BASE_DIR, "data", "exg_mapnames.json")


def app_dir():
    """程序所在目录：onefile 打包时 sys.executable 指向 exe 本体（可写、重启后仍在），
    源码运行时就是本目录。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return BASE_DIR


def remote_files():
    """云端译名表的候选位置，按优先级：
      ① 程序旁 data\\mapnames_remote.json —— 主程序拉取后落这里（持久）
      ② 随包内置的那份（若有）—— 兜底
    """
    out = [os.path.join(app_dir(), "data", "mapnames_remote.json")]
    if os.path.normcase(os.path.abspath(REMOTE_FILE)) != os.path.normcase(os.path.abspath(out[0])):
        out.append(REMOTE_FILE)
    return out

# ─────────────────── 1. 精选整名 ───────────────────
MAP_NAMES = {
    # —— 后室系列 ——
    "ze_backrooms": "后室",
    "ze_backrooms_insomnia": "后室2：失眠症",
    "ze_backrooms_deathbed": "后室3：弥留之际",
    "ze_backrooms_deathbed_v1": "后室3：弥留之际",
    "ze_backroom_level4_v1": "后室：第4层",
    "ze_theback_bureau": "后室：档案局",
    "ze_devil_may_cry": "鬼泣",
    "ze_ffvii_fako_reactor": "最终幻想7：魔晄炉",
    "ze_ffvii_mako_reactor_v5_3": "最终幻想7：魔晄炉",
    "ze_ffvii_mako_reactor_v6_p": "最终幻想7：魔晄炉",
    "ze_ffvii_malgo_reactor": "最终幻想7：魔晄炉",
    "ze_aepp_nano_grid2_p": "纳米电网2",
    "ze_croc2_sailor_village": "鳄鱼2：水手村",
    "ze_crimson_azure_nexus": "绯红苍穹枢纽",
    "ze_descent_into_cerberon_p": "深入地狱犬",
    "ze_endemic": "疫病",
    "ze_steyliff_grove_yk": "斯基利弗树林",
    # 2026-11-09 EXG 转正图：官方已收录但译名暂缺，先用 EXG 源给的 CnName
    # （官方表后补译名后会按优先级自动切换到官方名）
    "ze_exit8": "逃离8号出口",
    "ze_fe8_sacred_stones": "火焰之纹章:圣魔之光石",
    "ze_shadow_moses": "合金装备5：影子摩西",
    "ze_x_game_room": "电竞房",
    "ze_exit_this_earths_atomosphere_p": "逃离地球大气层",
    "ze_ffxii_mt_bur_omisace_v6": "最终幻想12：布尔山",
    "ze_ffxii_paramina_rift": "最终幻想12：帕拉米纳裂谷",
    "ze_inboxed_p": "身法茶鸡的噩梦",
    "ze_cube_defense": "方块防守",
    "ze_desperate_soul": "母神悲歌",
    "ze_dark_souls": "黑暗之魂1",
    "ze_dark_souls2": "黑暗之魂2",
    "ze_sky_fantasy_v1": "天空幻想",
    "ze_blue_magic_castle": "蓝色魔法城堡",
    "ze_evil_mansion_p": "恶灵庄园",
    # —— 逃生系列 ——
    "ze_panic_escape_p": "恐慌逃生",
    "ze_lila_panic_escape_p": "莉拉：恐慌逃生",
    "ze_atix_panic_p": "阿提克斯恐慌",
    "ze_atix_panic_2017_p": "阿提克斯恐慌2017",
    "ze_hazard_escape_p": "险境逃生",
    "ze_minecraft_escape": "我的世界：逃脱",
    "ze_minecraft_panic": "我的世界：惊魂",
    "ze_minecraft_manor_panic": "我的世界：庄园惊魂",
    "ze_sewer_escape_p": "下水道逃生",
    "ze_mountain_escape_snow": "雪山逃生",
    "ze_maontain_escape": "登山逃生",
    "ze_mountain_ultimate": "群山终极逃生",
    "ze_ocean_base_escape_p": "海底基地逃生",
    "ze_boat_escape_ultimate": "终极船只逃生",
    "ze_boatescape_ultimate": "终极船只逃生",
    "ze_boatescape101_p": "船只逃生101",
    "ze_boatescape777": "船只逃生777",
    "ze_boatescape888": "船只逃生888",
    "ze_boatescape999": "船只逃生999",
    "ze_rocket_escape_p": "火箭逃生",
    "ze_newyork_escape_p": "纽约逃生",
    "ze_venice_escape_p": "威尼斯逃生",
    "ze_sorrento_escape_p": "索伦托逃生",
    "ze_sorrento_escape_2016_p": "索伦托逃生2016",
    "ze_rooftop_madness_p": "天台狂潮",
    "ze_rooftop_rogue_ws": "天台游侠",
    "ze_rooftop_runaway1_p": "天台逃亡1",
    "ze_rooftop_runaway2_p": "天台逃亡2",
    "ze_temple_escape_p": "神庙逃生",
    "ze_trainescape_p": "列车逃生",
    "ze_trap_escape_p": "陷阱逃生",
    "ze_slender_escape_p": "瘦长鬼影逃生",
    "ze_titanic_escape_p": "泰坦尼克逃生",
    "ze_titanic_sweet_dreams": "泰坦尼克：甜蜜梦境",
    "ze_military_escape_p": "军事基地逃生",
    "ze_prisonbreak_rescue": "越狱营救",
    "ze_thelostworld_redux_p": "失落世界：重制版",
    "ze_project_codex": "密码计划",
    "ze_project_codex_z": "密码计划 Z",
    # —— 冲浪图 ——
    "ze_surf_facility_v2_3": "冲浪：设施",
    "ze_surf_facility_p": "冲浪：设施",
    "ze_surf_cherry_blossom": "冲浪：樱",
    "ze_surf_daybreak": "冲浪：破晓",
    "ze_surf_danger_p": "冲浪：危机",
    "ze_surf_froyo": "冲浪：冰酸奶",
    "ze_surf_froyo_lite": "冲浪：轻酸奶",
    "ze_surf_gypt_p": "冲浪：埃及",
    "ze_surf_happy": "快乐滑翔",
    "ze_surf_happy_2_newbie_village": "快乐滑翔2：新手村",
    "ze_surf_outside": "冲浪：外界",
    "ze_surf_sahok": "冲浪：沙霍克",
    "ze_surf_saltfish": "冲浪：咸鱼",
    "ze_surf_sky_islands": "冲浪：天空群岛",
    "ze_surf_soft": "冲浪：软软",
    "ze_surf_sparks_cs2": "冲浪：火花",
    "ze_surf_vortex_p": "冲浪：漩涡",
    "ze_surf_okitsu_shonyudo": "冲浪：冲津钟乳洞",
    "ze_surf_shonyudo_v1_cs2": "冲浪：钟乳洞",
    "ze_surf_operation_deterioration": "冲浪：恶化行动",
    "ze_surf_concrete": "冲浪：混凝土",
    "ze_surf_auv": "冲浪：深海探测器",
    "ze_mlgsurf": "职业冲浪",
    # —— 寂静岭 / 生化危机系列 ——
    "ze_silent_hill_2_illusion": "寂静岭2：幻象",
    "ze_silent_hill_2_rengurn": "寂静岭2：归来",
    "ze_silent_hill_3_dawn": "寂静岭3：黎明",
    "ze_silent_hill_3_dawn_full": "寂静岭3：黎明 完整版",
    "ze_silent_hill_3_flee": "寂静岭3：逃离",
    "ze_silent_hill_blackblood": "寂静岭：黑血",
    "ze_silent_hill_rengurn": "寂静岭：归来",
    "ze_silenthill_pt": "寂静岭 P.T.",
    "ze_resident_evil_3": "生化危机3",
    "ze_biohazard2_rpd_004_p": "生化危机2：警局",
    "ze_biohazard2_sewer_004": "生化危机2：下水道",
    "ze_biohazard_manor_004_p": "生化危机：洋馆",
    "ze_raccoon_facility_p": "浣熊市设施",
    # —— 魔戒系列 ——
    "ze_lotr_helms_deep_p": "魔戒：圣盔谷",
    "ze_lotr_isengard": "魔戒：艾森加德",
    "ze_lotr_minas_tirith": "魔戒：米那斯提力斯",
    "ze_lotr_minas_tiret_p": "魔戒：米那斯提力斯",
    "ze_lotr_minas_tirith_p": "魔戒：米那斯提力斯",
    "ze_lotr_minas_tirith_cs2": "魔戒：米那斯提力斯 CS2",
    "ze_lotr_minas_tiret_p2": "魔戒：米那斯提力斯2",
    "ze_lotr_mines_of_moria_p": "魔戒：摩瑞亚矿坑",
    "ze_lotr_mirkwood_p": "魔戒：幽暗密林",
    "ze_lotr_mount_doom_p": "魔戒：末日火山",
    # —— FF / DQ 等 ——
    "ze_ffvii_midgar": "最终幻想7：米德加",
    "ze_ffvii_slums": "最终幻想7：贫民窟",
    "ze_ffxii_feywood_briefing_p": "最终幻想12：幻影森林",
    "ze_ffxii_phon_coast": "最终幻想12：冯海岸",
    "ze_ffxiv_xelphatol": "最终幻想14：谢尔法托尔",
    "ze_icecap_escape_ia_super": "冰帽逃脱 超级版",
    "ze_incident_seasons": "四季事件簿",
    # —— 恶灵堡垒 obfuscated（obf）系列 ——
    "ze_obf_npst_v1": "梦魇行动1",
    "ze_obf_npst_v2": "梦魇行动2",
    "ze_obff_npst_v24": "梦魇行动2.4",
    "ze_obj_npst_v1": "梦魇行动1",
    "ze_obf_filth_v1": "污秽",
    "ze_obf_insane": "疯狂",
    "ze_obf_rampage_v2": "狂暴2",
    "ze_obf_rampage_v24": "狂暴2.4",
    "ze_obf_rampage_v2_legacy": "狂暴2 经典版",
    "ze_obf_rescape": "梦魇逃脱",
    # —— 崩坏 / 明日方舟 / 蓝色archive 等 ——
    "ze_bh3rd_babel_z": "崩坏3：巴别塔",
    "ze_bh3rd_cyberpunk_z": "崩坏3：赛博朋克",
    "ze_bh3rd_nagazoracity_z": "崩坏3：长空市",
    "ze_arknights_caerula_arbor": "明日方舟：覆潮之下",
    "ze_arknights_initium": "明日方舟：初始",
    "ze_arknights_sows": "明日方舟：怀黍离",
    "ze_bluearchive_abydos": "蔚蓝档案：阿拜多斯",
    "ze_bluearchive_abydos_b1": "蔚蓝档案：阿拜多斯",
    "ze_ruin_of_black_stone": "黑石遗迹",
    "ze_bang_dream_mygo": "BanG Dream! MyGO!!!!!",
    "ze_aot_trost_v8": "进击的巨人：托洛斯特区",
    "ze_aot_trost_v6r": "进击的巨人：托洛斯特区 重制",
    "ze_psycho_pass": "心理测量者",
    "ze_undertale_sans_final": "传说之下：Sans 决战",
    "ze_ponyo_zk_fapescape_p": "崖上的波妞逃生",
    "ze_zk_fapescape_p": "Fapescape 逃生",
    "ze_zk_mall_of_zombies_p": "僵尸商场",
    "ze_bioshock_v6_cs2": "生化奇兵 CS2",
    "ze_blackmesa_escape_p": "黑山基地逃生",
    "ze_blackmesa_remix_cs2": "黑山基地 重混版",
    "ze_portal_story_p": "传送门：故事版",
    "ze_aperturescience_p": "光圈科技",
    "ze_miside": "MiSide",
    "ze_lethal_company": "致命公司",
    "ze_scp_containment_breach": "SCP：收容失效",
    "ze_outlast": "逃生 (Outlast)",
    "ze_trepang": "极度恐慌 (Trepang2)",
    "ze_sekiro": "只狼",
    "ze_ultrakill": "ULTRAKILL",
    "ze_misaka": "御坂美琴",
    "ze_misaka2_reborn": "御坂美琴2：重生",
    "ze_squid_game": "鱿鱼游戏",
    "ze_pokemon_kanto_v1": "宝可梦：关都地区",
    "ze_mario_tower_p": "马里奥之塔",
    "ze_luigismansion_p": "路易吉洋馆",
    "ze_peach_castle_n64": "桃花公主城堡",
    "ze_peach_insanity_n64": "桃花公主城堡 疯狂版",
    "ze_bigboo_n64": "大幽灵 N64",
    
    "ze_ocarina_of_time": "塞尔达：时光之笛",
    "ze_n64_goldeneye_go": "黄金眼 N64",
    "ze_pd2_crime_art": "收获日2：罪恶艺术",
    "ze_minecraft_dragon_castle": "我的世界：巨龙城堡",
    "ze_minecraft_dreamland": "我的世界：梦境",
    "ze_minecraft_drifts": "我的世界：漂流",
    "ze_minecraft_flood_escape": "我的世界：洪水逃生",
    "ze_minecraft_journey_v1": "我的世界：旅程",
    "ze_minecraft_lucky_blocks": "我的世界：幸运方块",
    "ze_minecraft_p": "我的世界",
    "ze_minecraft_run": "我的世界：奔跑",
    "ze_minecraft_sakura": "我的世界：樱",
    "ze_minecraft_universe": "我的世界：宇宙",
    "ze_minecraft_adventure": "我的世界：冒险",
    "ze_minecraft_hortus_de_escapismo": "我的世界：逃逸花园",
    "ze_plants_vs_zombies": "植物大战僵尸",
    "ze_p_v_z": "植物大战僵尸",
    "ze_bathroom": "洗手间惊魂",
    "ze_breakable_p": "易碎世界",
    "ze_downstairs": "楼下",
    "ze_20_seconds_v1": "20秒",
    "ze_30_seconds_p": "30秒",
    "ze_2049": "2049",
    "ze_203_factory": "203工厂",
    "ze_2021_xmas_world_p": "2021圣诞世界",
    "ze_2025_xmas_world": "2025圣诞世界",
    "ze_8bit": "8比特",
    "ze_a_e_s_t_h_e_t_i_c_p": "美学",
    "ze_aware": "觉醒",
    "ze_awaker": "唤醒者",
    "ze_mota": "魔塔",
    "ze_mindtree": "心灵之树",
    "ze_omega_p": "欧米伽",
    "ze_umbra": "本影",
    "ze_loom": "织机",
    "ze_lorem_ipsum_p": "虚拟文本",
    "ze_oneiros_p": "梦神",
    "ze_one_dream_machine": "一台造梦机",
    "ze_ny_marathon_cs2": "纽约马拉松",
    "ze_timeshifter": "时空行者",
    "ze_timesink": "时间黑洞",
    "ze_sisyphus": "西西弗斯",
    "ze_castlevania": "恶魔城",
    "ze_castlevania_nes": "恶魔城 FC版",
    "ze_shaurma_v3": "沙威玛",
    "ze_chicken_kingdom": "小鸡王国",
    "ze_chicken_nugget": "鸡块",
    "ze_chicken_lords_tower_p": "鸡老大之塔",
    "ze_christmas_escape": "圣诞逃生",
    "ze_christmas_infection_p": "圣诞感染",
    "ze_christmas_p": "圣诞节",
    "ze_winter": "凛冬",
    "ze_winter_warehouse_p": "冬日仓库",
    "ze_siberia_1990_p": "西伯利亚1990",
    "ze_samoa": "萨摩亚",
    "ze_watagi_sanatorium": "疗养院",
    "ze_watagi_tunnel_rewind": "疗养院隧道 倒带",

    # ─────────── 2026-09-28 补齐 ───────────
    # 此前地图库 / 地图实体预览里仍显示原始英文名的图（共 112 张：ze 44 / ttt 42 / mg 26）。
    # 一部分是作品名或社区通称（鬼灭之刃 / 约会大作战 / 最终幻想 等），
    # 其余按地名与词面意译；将来若发现更准确的叫法，改这里或
    # data/mapnames.json（用户层，优先级最高）即可。
    # —— ze ——
    "ze_alien_shooter": "外星射手",
    "ze_atl_lgnition_a1": "亚特兰蒂斯：点火",
    "ze_beyond_horizon": "超越地平线",
    "ze_beyond_the_boundary": "越界",
    "ze_changing_room": "更衣室",
    "ze_chenbai_alph": "沉白",
    "ze_color_levels": "色彩关卡",
    "ze_contradiction_spiral": "矛盾螺旋",
    "ze_date_a_live": "约会大作战",
    "ze_demon_slayer": "鬼灭之刃",
    "ze_dnd_hydra_z": "龙与地下城：九头蛇",
    "ze_ffvii_cosmo_canyon_v2": "最终幻想7：宇宙峡谷",
    "ze_ffxii_ridorana_cataract": "最终幻想12：里多拉纳大瀑布",
    "ze_ffxiv_the_orbonne_monastery": "最终幻想14：奥伯恩修道院",
    "ze_flat_surviva": "平地生存",
    "ze_gtasa_police_station_2_m": "圣安地列斯：警局2",
    "ze_gtasa_police_station_remix_m": "圣安地列斯：警局 重混",
    "ze_guye_room": "谷野房间",
    "ze_halo3_thestorm": "光环3：风暴",
    "ze_hlc_tsunami_v1": "海啸",
    "ze_hold2_boring_z": "据点2：无聊",
    "ze_honkai_impact_3rd_babel_z": "崩坏3：巴别塔",
    "ze_honkai_impact_3rd_cyberpunk_z": "崩坏3：赛博朋克",
    "ze_honkai_impact_changkongshi": "崩坏3：长空市",
    "ze_honkai_impact_tqs": "崩坏3：天穹市",
    "ze_imperial_sanctum": "帝国圣殿",
    "ze_kraznov_poopata_p": "克拉斯诺夫：波帕塔",
    "ze_labor_trading_factory": "劳动力交易工厂",
    "ze_last_man_standing_p": "最后生还者",
    "ze_little_trip": "小小旅程",
    "ze_mirrors_edge_reborn_p": "镜之边缘：重生",
    "ze_mo3_time_capsule": "时间胶囊",
    "ze_nuclear_site_survie_by_gm": "核电站生存",
    "ze_obj_ouroboros_apollyon": "衔尾蛇：亚玻伦",
    "ze_pc": "个人电脑",
    "ze_rt4_hessel_valley": "赫塞尔山谷",
    "ze_sex_mod_hentai_beachescape_camper_p": "海滩营地",
    "ze_sit_caelum_paradisus": "天堂乐园",
    "ze_stardust_a03": "星尘",
    "ze_tear_of_tide": "潮汐之泪",
    "ze_thorn_final_song": "荆棘：终曲",
    "ze_thorny_torch": "荆棘火炬",
    "ze_ut2004_convoy_p": "虚幻2004：护航",
    "ze_zandalar_forever": "赞达拉永恒",
}

# ─────────────────── 2. 词根词典 ───────────────────
WORDS = {
    "escape": "逃生", "run": "狂奔", "panic": "恐慌", "rescue": "营救",
    "surf": "冲浪", "facility": "设施", "parkour": "跑酷",
    "minecraft": "我的世界", "n64": "N64",
    "temple": "神庙", "castle": "城堡", "palace": "宫殿", "tower": "塔",
    "town": "小镇", "city": "城市", "island": "岛", "islands": "群岛",
    "canyon": "峡谷", "mountain": "山", "ice": "冰", "icecap": "冰帽",
    "abyss": "深渊", "sewer": "下水道", "sewers": "下水道",
    "factory": "工厂", "lab": "实验室", "basement": "地下室",
    "train": "列车", "boat": "船", "ship": "船", "rocket": "火箭",
    "prison": "监狱", "mansion": "庄园", "manor": "庄园", "church": "教堂",
    "hospital": "医院", "hotel": "旅馆", "office": "办公室",
    "silent": "寂静", "hill": "岭", "hills": "丘陵",
    "world": "世界", "dream": "梦境", "dreamland": "梦境",
    "night": "夜", "nightmare": "梦魇", "insomnia": "失眠症",
    "backrooms": "后室", "dark": "黑暗", "light": "光",
    "death": "死亡", "dead": "亡者", "life": "生", "survival": "生存",
    "final": "最终", "last": "最后", "first": "初始", "second": "第二",
    "winter": "冬", "summer": "夏", "autumn": "秋", "spring": "春",
    "snow": "雪", "rain": "雨", "storm": "风暴", "fire": "火",
    "water": "水", "flood": "洪水", "ocean": "海洋", "sea": "海",
    "sky": "天空", "star": "星", "stars": "群星", "moon": "月",
    "sun": "日", "cloud": "云", "wind": "风", "earth": "大地",
    "christmas": "圣诞", "xmas": "圣诞", "halloween": "万圣节",
    "party": "派对", "fun": "欢乐", "happy": "快乐", "sad": "悲伤",
    "chicken": "小鸡", "penguin": "企鹅", "cat": "猫", "dog": "狗",
    "zombie": "僵尸", "zombies": "僵尸", "santa": "圣诞老人",
    "temple2": "神庙2",
    "secret": "秘密", "hidden": "隐藏", "lost": "失落",
    "abandoned": "废弃", "broken": "破碎", "frozen": "冰封",
    "burning": "燃烧", "sacred": "神圣", "cursed": "被诅咒的",
    "ancient": "远古", "old": "古老", "new": "新", "mini": "迷你",
    "super": "超级", "ultimate": "终极", "extreme": "极限",
    "remake": "重制", "remastered": "重制版", "rewind": "倒带",
    "reborn": "重生", "redux": "重制版", "return": "回归",
    "invasion": "入侵", "defense": "守卫", "defend": "防守",
    "attack": "进攻", "war": "战争", "battle": "战斗",
    "quest": "探索", "journey": "旅程", "story": "物语", "tale": "传说",
    "legend": "传说", "myth": "神话", "adventure": "冒险",
    "rooftop": "天台", "bridge": "桥", "gate": "大门", "door": "门",
    "eye": "之眼", "heart": "之心", "soul": "灵魂", "souls": "之魂", "spirit": "幽魂",
    "blood": "血", "flesh": "血肉", "bone": "骨",
    "kingdom": "王国", "empire": "帝国", "land": "之地", "world2": "世界2",
    "up": "向上", "down": "向下", "downstairs": "楼下", "upstairs": "楼上",
    "out": "逃出", "inside": "内部", "outside": "外界",
    "black": "黑", "white": "白", "red": "红", "blue": "蓝",
    "green": "绿", "yellow": "黄", "pink": "粉", "purple": "紫",
    "silver": "银", "golden": "黄金", "gold": "黄金",
    "one": "一", "two": "二", "three": "三", "four": "四", "five": "五",
    "six": "六", "seven": "七", "eight": "八", "nine": "九", "ten": "十",
    "minas": "米那斯", "tirith": "提力斯", "moria": "摩瑞亚",
    "doom": "末日", "wrath": "怒火", "chaos": "混沌", "order": "秩序",
    "hope": "希望", "fear": "恐惧", "madness": "疯狂", "panic2": "恐慌2",
    "incident": "事件簿", "seasons": "四季", "season": "季节",
    "tower2": "塔2", "project": "计划", "protocol": "协议",
    "core": "核心", "base": "基地", "station": "空间站",
    "power": "能量", "energy": "能源", "machine": "机器",
    "robot": "机器人", "cyber": "赛博", "punk": "朋克",
    "future": "未来", "past": "过去", "time": "时间", "space": "太空",
    "planet": "行星", "mars": "火星", "moon2": "月2",
    "forest": "森林", "jungle": "丛林", "desert": "沙漠",
    "valley": "山谷", "lake": "湖", "river": "河", "pool": "泳池",
    "pools": "泳池", "beach": "海滩", "cave": "洞穴", "mine": "矿坑",
    "farm": "农场", "garden": "花园", "park": "公园",
    "amazon": "亚马逊", "industry": "工业区", "complex": "建筑群",
    "rampage": "狂暴", "onslaught": "猛攻", "assault": "突击",
    "the": "", "of": "之", "a": "", "an": "", "and": "与", "de": "之",
    "npst": "梦魇行动", "obf": "", "obj": "", "ze": "", "cs2": "CS2",
    "csgo": "CSGO", "v": "",
    # 2026-09-28 补：通用地名 / 玩法词（ze 系列里也有用）
    "village": "村庄", "school": "学校", "subway": "地铁",
    "stadium": "体育场", "terminal": "航站楼", "typhoon": "台风",
}

_NUM_CN = {1: "1", 2: "2", 3: "3", 4: "4", 5: "5", 6: "6", 7: "7",
           8: "8", 9: "9", 0: "0"}

_user_cache = {"at": 0.0, "names": {}, "rat": 0.0, "rnames": {}}
# EXG 译名表是随包只读文件，不会在运行期变，读到就常驻（None = 还没读过）
_exg_cache = {"names": None}

# ─────────────────── 3. 完美平台译名表 ───────────────────
try:
    with io.open(PLATFORM_FILE, encoding="utf-8") as _fh:
        PLATFORM_NAMES = json.load(_fh) or {}
except Exception:                                          # noqa: BLE001
    PLATFORM_NAMES = {}


def _user_names():
    """用户自定义 data/mapnames.json（map -> 中文名），10 秒缓存。"""
    if not os.path.exists(USER_FILE):
        return {}
    mt = os.path.getmtime(USER_FILE)
    if _user_cache["at"] != mt:
        try:
            with io.open(USER_FILE, encoding="utf-8") as fh:
                _user_cache["names"] = json.load(fh) or {}
        except Exception:                                      # noqa: BLE001
            _user_cache["names"] = {}
        _user_cache["at"] = mt
    return _user_cache["names"]


def _remote_names():
    """云端热更表（程序旁 data/mapnames_remote.json 优先），按 (路径, mtime) 缓存。"""
    pick = None
    for p in remote_files():
        if os.path.exists(p):
            pick = p
            break
    if not pick:
        return {}
    key = (pick, os.path.getmtime(pick))
    if _user_cache.get("rat") != key:
        try:
            with io.open(pick, encoding="utf-8") as fh:
                _user_cache["rnames"] = json.load(fh) or {}
        except Exception:                                      # noqa: BLE001
            _user_cache["rnames"] = {}
        _user_cache["rat"] = key
    return _user_cache.get("rnames") or {}


def _exg_names():
    """EXG 图池补充图的译名（随包内置，只读；进程内缓存一次）。"""
    if _exg_cache["names"] is None:
        try:
            with io.open(EXG_FILE, encoding="utf-8") as fh:
                _exg_cache["names"] = json.load(fh) or {}
        except Exception:                                      # noqa: BLE001
            _exg_cache["names"] = {}
    return _exg_cache["names"]


def effective_names():
    """当前生效的**查表部分**译名（不含词根合成），供 /api/mapnames 下发。
    顺序与 cn() 一致：后者覆盖前者。"""
    out = {}
    out.update(_exg_names())              # 优先级最低：EXG 兜底层
    out.update(MAP_NAMES)
    out.update(PLATFORM_NAMES)
    out.update(_remote_names())
    out.update(_user_names())
    return out


def _strip(name):
    """去掉 ze_ / mg_ / ze_ 等前缀与版本尾巴，返回词条列表。"""
    base = re.sub(r"^(ze|mg|fo|zm|ka|dl)_", "", (name or "").strip().lower())
    toks = [t for t in re.split(r"[_.\-\s]+", base) if t]
    return toks


def _compose(toks):
    parts, unknown = [], 0
    i = 0
    while i < len(toks):
        t = toks[i]
        # 词典优先匹配两词组合（如 silent hill）
        if i + 1 < len(toks):
            two = t + " " + toks[i + 1]
            if two in WORDS:
                v = WORDS[two]
                if v:
                    parts.append(v)
                i += 2
                continue
        if t in WORDS:
            v = WORDS[t]
            if v:
                parts.append(v)
        elif re.fullmatch(r"v\d+(\.\d+)*|v\d+_\d+", t):
            pass                      # 版本号不翻
        elif t.isdigit():
            parts.append(t)
        elif len(t) <= 2:
            pass                      # 单字母标记（a1/z/l 之类）不翻
        else:
            parts.append(t)
            unknown += 1
        i += 1
    out = " ".join(p for p in parts if p)
    return out, unknown


def cn(map_name):
    """地图中文名：用户自定义 -> 云端表 -> 平台表 -> 精选整名 -> EXG 表 -> 词根合成。
    翻不出返回 None。"""
    if not map_name:
        return None
    key = map_name.strip().lower()
    # ttt_（恐怖分子小镇）/ mg_（小游戏）两类不做译名 —— 只做 ze 系列，
    # 保持原名显示（2026-09-28 用户确认）。
    if key.startswith(("ttt_", "mg_")):
        return None
    un = _user_names()
    if key in un:
        return un[key]
    rn = _remote_names()
    if key in rn:
        return rn[key]
    if key in PLATFORM_NAMES:
        return PLATFORM_NAMES[key]
    if key in MAP_NAMES:
        return MAP_NAMES[key]
    xn = _exg_names()                     # EXG 图池补充图（官方表里没有的那批）
    if key in xn:
        return xn[key]
    text, unknown = _compose(_strip(key))
    # 含未知词或没有产出 -> 视为翻不出（宁可显示原名，不要半中半英）
    if not text or unknown > 1 or text == key:
        return None
    return text


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    for m in ("ze_backrooms_insomnia", "ze_downstairs", "ze_panic_escape_p",
              "ze_obf_npst_v1", "ze_incident_seasons", "ze_icecap_escape_ia_super",
              "ze_surf_facility_v2_3", "ze_hazard_escape_p", "ze_breakable_p",
              "ze_silent_hill_2_illusion", "ze_minecraft_dragon_castle",
              "ze_lotr_minas_tirith_p", "ze_notexist_xyzzy_qwerty"):
        print("%-34s -> %s" % (m, cn(m)))
