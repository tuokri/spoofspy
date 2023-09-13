import logging

import numpy as np

from spoofspy import db

logger = logging.getLogger(__name__)

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
    0.02,
    0.06,
    0.2,
    0.3,
    0.4,
    1.0,
    5.0,
])


def _clamp(x: float, x_min: float, x_max: float) -> float:
    if x < x_min:
        return x_min
    elif x > x_max:
        return x_max
    return x


def eval_trust_score(state: db.models.GameServerState) -> float:
    """Evaluate server state trust score in range [0.0, 1.0].
    1.0 is perfect score and 0.0 is the worst possible score.
    """
    score = 1.0
    players = state.players  # Steam only.

    no_response_penalty = 0.33
    penalties: list[float] = []
    weights: list[float] = []

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

    return _clamp(score, 0.0, 1.0)
