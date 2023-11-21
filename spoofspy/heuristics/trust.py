import ipaddress
import logging

import numpy as np

from spoofspy import db

logger = logging.getLogger(__name__)

# TODO: store penalty curve and algorithm versions in db?
#   - Ability do discern evaluations done on different versions.

# Player count difference penalty curve x values.
player_count_x = np.array([
    0,
    2,
    5,
    12,
    20,
    32,
    64,
    128,
])
# Player count difference penalty curve y values.
player_count_y = np.array([
    0.0,
    0.01,
    0.06,
    0.2,
    0.3,
    0.4,
    1.0,
    5.0,
])

ww_bots = {
    "Perttu",
    "Antti",
    "Mikko",
    "Tuukka",
    "Joni",
    "Matti",
    "Luukas",
    "Valtteri",
    "Miika",
    "Seppo",
    "Kyllian",
    "Ismo",
    "Manolis",
    "Juuso",
    "Veeti",
    "Pessi",
    "Joel",
    "Leevi",
    "Nalle",
    "Aapo",
    "Mirko",
    "Eemeli",
    "Kristian",
    "Hemmu",
    "Pasi",
    "Oskari",
    "Petri",
    "Tuomo",
    "Mauri",
    "Topi",
    "Juhani",
    "Perkele",
    "Anton",
    "Vladimir",
    "Pavel",
    "Yuri",
    "Grigoriy",
    "Vasili",
    "Aleksei",
    "Georgiy",
    "Karpov",
    "Anatoli",
    "Il'ya",
    "Sergey",
    "Nikolai",
    "Konstantin",
    "Artyom",
    "Aleksandr",
    "Petr",
    "Gennadiy",
    "Viktor",
    "Evgeny",
    "Valentin",
    "Iosif",
    "Boris",
    "Andrei",
    "Ivan",
    "Matvei",
    "Yakov",
    "Ilich",
    "Stepan",
    "Fedor",
    "Mikhail",
    "Dimitri",
}

rs2_bots = {
    "Trang",
    "Giang",
    "Vuong",
    "Huu",
    "Hien",
    "Duc",
    "Trong",
    "Tuan",
    "Phong",
    "Hai",
    "Thao",
    "Cuong",
    "Binh",
    "Phuoc",
    "Anh",
    "Danh",
    "Hung",
    "Nhat",
    "Quan",
    "Vien",
    "Chinh",
    "Lanh",
    "Bao",
    "Ngai",
    "Sang",
    "Thanh",
    "Sinh",
    "Xuan",
    "Dien",
    "Chien",
    "Huynh",
    "Minh",
    "John",
    "Adam",
    "Bill",
    "Stuart",
    "Jack",
    "Simon",
    "David",
    "Richard",
    "Alan",
    "Floyd",
    "Adam",
    "Rob",
    "Ross",
    "George",
    "Ben",
    "Javier",
    "Dan",
    "Thomas",
    "Keith",
    "Sam",
    "Joe",
    "Don",
    "Toby",
    "James",
    "Justyn",
    "Lewis",
    "Nathan",
    "Pedro",
    "Alex",
    "Mike",
    "Ken",
    "Leo",
}

gom4_bots = rs2_bots | {
    "John",
    "Adam",
    "Bill",
    "Stuart",
    "Jack",
    "Simon",
    "David",
    "Richard",
    "Alan",
    "Floyd",
    "Adam",
    "Rob",
    "Ross",
    "George",
    "Ben",
    "Javier",
    "Dan",
    "Thomas",
    "Keith",
    "Sam",
    "Joe",
    "Don",
    "Toby",
    "James",
    "Justyn",
    "Lewis",
    "Nathan",
    "Pedro",
    "Alex",
    "Mike",
    "Ken",
    "Leo",
    "Young-Su",
    "Seong-ho",
    "Hong-Hyeon",
    "Jung-Woo",
    "Yeong-Gil",
    "Man-Won",
    "Yong-Sik",
    "Jin-Tae",
    "Tae-Su",
    "Jung-Geun",
    "Cheol-su",
    "Chang-Rok",
    "Tae-In",
    "Won-Gyun",
    "Jae-Young",
    "Gyu-Tae",
    "Mun-Seop",
    "Jae-Pil",
    "Byeong-Hoon",
    "Woo-Il",
    "Myeong-Hwan",
    "Hwa-Jong",
    "Woo-Sik",
    "In-Heon",
    "Ju-Ryong",
    "Gyu-Hak",
    "Young-Il",
    "Ho-Seong",
    "Sang-Su",
    "Jin-Seok",
    "Moo-Gyeong",
    "Hee-Gyun",
    "Trang",
    "Giang",
    "Vuong",
    "Huu",
    "Hien",
    "Duc",
    "Trong",
    "Tuan",
    "Phong",
    "Hai",
    "Thao",
    "Cuong",
    "Binh",
    "Phuoc",
    "Anh",
    "Danh",
    "Hung",
    "Nhat",
    "Quan",
    "Vien",
    "Chinh",
    "Lanh",
    "Bao",
    "Ngai",
    "Sang",
    "Thanh",
    "Sinh",
    "Xuan",
    "Dien",
    "Chien",
    "Huynh",
    "Minh",
    "Khamtai",
    "Kaysone",
    "Phoumi",
    "Deuane",
    "Kanoa",
    "Satasin",
    "Kale",
    "Nugoon",
    "Pekelo",
    "Paxathipatai",
    "Keanu",
    "Makani",
    "Xaisomboun",
    "Kahoku",
    "Kye",
    "Bane",
    "Sengprachanh",
    "Fa Ngum",
    "Thongsavanh",
    "Akamu",
    "Kapono",
    "Siphandon",
    "Kelii",
    "Phonesavanh",
    "Mao",
    "Loe",
    "Kawaii",
    "Kaipo",
    "Koa",
    "Malo",
    "Ikaika",
    "Kaipo",
}


def _clamp(x: float, x_min: float, x_max: float) -> float:
    if x < x_min:
        return x_min
    elif x > x_max:
        return x_max
    return x


def _bot_count(
        pi_objs_actual: list[tuple[int, dict[str, str]]],
        bot_names: set[str],
) -> int:
    bot_count = 0
    for _, pi_obj in pi_objs_actual:
        if pi_obj["p"] == "STEAM" and (pi_obj["n"] in bot_names):
            bot_count += 1
    return bot_count


# NOTE: hard-coding score for these now, need to improve
# score evaluation algorithm to detect these better.
_bad = (
    ipaddress.IPv4Address("51.222.28.26"),
    ipaddress.IPv4Address("51.79.173.138"),
    ipaddress.IPv4Address("51.195.45.25"),
    ipaddress.IPv4Address("146.59.94.15"),
)


def eval_trust_score(state: db.models.GameServerState) -> float:
    """Evaluate server state trust score in range [0.0, 1.0].
    1.0 is perfect score and 0.0 is the worst possible score.

    TODO: (IMPORTANT/STABILITY):
      - make this function exception safe, return null
        on failure and log it

    TODO: Advanced evaluation:
      - track player score and ping changes across a period

    TODO: use a2s_open_slots.

    TODO: there's potential for false positives and false
      negatives with bot name checking. Players can also
      have bot names. But does this really matter?
    """
    score = 1.0
    players = state.players  # Steam only.

    no_response_penalty = 0.33
    penalties: list[float] = []
    weights: list[float] = []
    is_ww = False
    is_gom3 = False
    is_gom4 = False

    muts = state.a2s_mutators_running or []
    muts = [mut.lower() for mut in muts]

    if state.game_server_address in _bad:
        logger.info("using hard-coded 0 for %s:%s",
                    state.game_server_address, state.game_server_port)
        return 0

    if (
            (state.game_server_address == ipaddress.IPv4Address("62.102.148.162"))
            and (state.game_server_port == 47411)
    ):
        logger.info("using hard-coded 0 for %s:%s",
                    state.game_server_address, state.game_server_port)
        return 0

    # Check known mutators/mods, be more lenient towards known bots.
    if (
            state.a2s_info_responded
            and state.map.startswith("WW")
            and state.a2s_map_name.startswith("WW")
    ):
        logger.info(
            "%s:%s seems to be running Winter War (%s), being more lenient with bot players",
            state.game_server_address, state.game_server_port, state.map)
        is_ww = True
    elif muts and ("gom3.u" in muts):
        is_gom3 = True
    elif muts and ("gom4.u" in muts):
        is_gom4 = True

    if is_gom3 or is_gom4:
        logger.info(
            "%s:%s seems to be running GOM (%s), being more lenient with bot players",
            state.game_server_address, state.game_server_port, state.a2s_mutators_running)

    if not state.secure:
        penalties.append(0.1)
        weights.append(1.0)

    if state.a2s_info_responded:
        apc = state.a2s_player_count  # Steam only.
        apc_diff = abs(players - apc)
        # noinspection PyTypeChecker
        penalties.append(np.interp(
            apc_diff,
            player_count_x,
            player_count_y,
        ))  # type: ignore[arg-type]
        weights.append(1.0)
    else:
        score -= no_response_penalty

    if state.a2s_rules_responded:
        # These include both, Steam and EOS.
        npc = state.a2s_num_public_connections
        nopc = state.a2s_num_open_public_connections
        conn_players = npc - nopc

        # PI_COUNT includes both platforms and non-player PIs.
        n_pi_count_diff = abs(state.a2s_pi_count - conn_players)

        # The server can report old PIs that have already left the
        # server, so we have to manually "slice" by PI_COUNT.
        pi_objs_actual = []
        for pi_idx, a2s_pi_obj in state.a2s_pi_objects.items():
            try:
                int_idx = int(pi_idx)
            except ValueError:
                continue
            if int_idx < state.a2s_pi_count:
                pi_objs_actual.append((int_idx, a2s_pi_obj))

        num_steam_pi_objs = 0
        num_eos_pi_objs = 0
        for pi_obj in pi_objs_actual:
            p = str(pi_obj[1]["p"]).lower()
            if p == "steam":
                num_steam_pi_objs += 1
            elif p == "eos":
                num_eos_pi_objs += 1
            else:
                # What the fuck?
                logger.error(
                    "invalid platform '%s' for object: %s",
                    p, pi_obj
                )

        steam_pi_diff = abs(players - num_steam_pi_objs)
        eos_pi_diff = abs((state.a2s_pi_count - players) - num_eos_pi_objs)

        # This is a stupid way of checking bots, but the servers
        # don't advertise their bot counts in any sensible way...
        if (steam_pi_diff > 2) and (n_pi_count_diff > 2):
            bot_count = 0

            if is_ww:
                bot_count = _bot_count(pi_objs_actual, ww_bots)
            elif is_gom3:
                bot_count = _bot_count(pi_objs_actual, rs2_bots)
            elif is_gom4:
                bot_count = _bot_count(pi_objs_actual, gom4_bots)

            penalty_fix = bot_count * 0.95
            if penalty_fix > 0:
                n_pi_count_diff = abs(n_pi_count_diff - penalty_fix)  # type: ignore[assignment]
                steam_pi_diff = abs(steam_pi_diff - penalty_fix)  # type: ignore[assignment]
                logger.info("%s:%s lowered n_pi_count_diff by %s, new value %s",
                            state.game_server_address,
                            state.game_server_port,
                            penalty_fix,
                            n_pi_count_diff)
                logger.info("%s:%s lowered steam_pi_diff by %s, new value %s",
                            state.game_server_address,
                            state.game_server_port,
                            penalty_fix,
                            steam_pi_diff)

        pi_count_conn_penalty = np.interp(
            n_pi_count_diff,
            player_count_x,
            player_count_y,
        )  # type: ignore[assignment]

        pi_count_conn_steam_penalty = np.interp(
            steam_pi_diff,
            player_count_x,
            player_count_y,
        )  # type: ignore[assignment]

        pi_count_conn_eos_penalty = np.interp(
            eos_pi_diff,
            player_count_x,
            player_count_y,
        )  # type: ignore[assignment]

        sub_penalty_avg = np.average(
            [
                pi_count_conn_penalty,
                pi_count_conn_steam_penalty,
                pi_count_conn_eos_penalty,
            ],
            weights=[
                3.0,
                2.5,
                1.0,
            ],
        )

        penalties.append(sub_penalty_avg)
        weights.append(3.0)

    else:
        score -= no_response_penalty

    if state.a2s_players_responded:
        # Steam only.
        num_a2s_players = len(state.a2s_players)
        n_a2s_p_diff = abs(num_a2s_players - players)

        # noinspection PyTypeChecker
        penalties.append(np.interp(
            n_a2s_p_diff,
            player_count_x,
            player_count_y,
        ))  # type: ignore[arg-type]
        weights.append(1.0)
    else:
        score -= no_response_penalty

    logger.info(
        "%s:%s: penalties, weights: %s, %s",
        state.game_server_address,
        state.game_server_port,
        penalties,
        weights,
    )

    for penalty, weight in zip(penalties, weights):
        score -= penalty * weight

    trust_score = _clamp(score, 0.0, 1.0)
    logger.info(
        "%s:%s: score: %s",
        state.game_server_address,
        state.game_server_port,
        trust_score,
    )

    return trust_score
