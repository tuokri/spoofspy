import numpy as np

from spoofspy import db

# Player count difference penalty curve x values.
player_count_x = np.array([
    2,
    5,
    12,
    20,
    32,
    64,
])
# Player count difference penalty curve y values.
player_count_y = np.array([
    0.05,
    0.06,
    0.07,
    0.08,
    0.1,
    0.2,
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
    players = state.players

    # TODO: use weighted averages!

    if state.a2s_info_responded:
        apc = state.a2s_player_count
        apc_diff = abs(players - apc)
        if apc_diff >= 2:
            score -= np.interp(
                apc_diff,
                player_count_x,
                player_count_y,
            )  # type: ignore[assignment]
    else:
        score -= 0.33

    if state.a2s_rules_responded:
        npc = state.a2s_num_public_connections
        nopc = state.a2s_num_open_public_connections
        c_players = npc - nopc

        conn_players_diff = abs(players - c_players)
        n_pi_count_diff = abs(state.a2s_pi_count - players)

        conn_players_penalty = np.interp(
            conn_players_diff,
            player_count_x,
            player_count_y,
        )  # type: ignore[assignment]

        n_pi_count_penalty = np.interp(
            n_pi_count_diff,
            player_count_x,
            player_count_y,
        )  # type: ignore[assignment]

        score -= np.average(
            [conn_players_penalty, n_pi_count_penalty],
            weights=[3.0, 1.0],
        )

    else:
        score -= 0.33

    if state.a2s_players_responded:
        num_a2s_players = len(state.a2s_players)

        n_a2s_p_diff = abs(num_a2s_players - players)

        score -= np.interp(
            n_a2s_p_diff,
            player_count_x,
            player_count_y,
        )
    else:
        score -= 0.33

    return _clamp(score, 0.0, 1.0)
