SELECT game_server_address,
       array_agg(game_server_port)          as game_server_port_agg,
       array_agg(last_week_avg_trust_score) as trust_score_agg
FROM (SELECT game_server_address,
             game_server_port,
             avg(avg_trust_score) AS last_week_avg_trust_score
      FROM (SELECT game_server_address,
                   game_server_port,
                   avg_trust_score,
                   rank() OVER (
                       PARTITION BY game_server_address, game_server_port
                       ORDER BY four_day_bucket DESC
                       )
            FROM (SELECT time_bucket('4 days', time) AS four_day_bucket,
                         avg(trust_score)            AS avg_trust_score,
                         game_server_address,
                         game_server_port
                  FROM game_server_state
                  WHERE game_server_state.trust_score IS NOT NULL
                  GROUP BY game_server_address, game_server_port, four_day_bucket
                  ORDER BY game_server_address, game_server_port, four_day_bucket DESC) AS gss_buckets) AS gss_ranked
      WHERE gss_ranked.rank = 1
        AND gss_ranked.avg_trust_score < :cutoff
      GROUP BY game_server_address, game_server_port) gss_avg_trust_groups
-- Where server is in set of servers last seen in 24 hours.
WHERE (game_server_address, game_server_port) IN (SELECT game_server_address, game_server_port
                                                  FROM (SELECT game_server_address,
                                                               game_server_port,
                                                               time,
                                                               rank() OVER (
                                                                   PARTITION BY game_server_address, game_server_port
                                                                   ORDER BY game_server_state.time DESC
                                                                   )
                                                        FROM game_server_state) AS gss_ranked_by_time
                                                  WHERE gss_ranked_by_time.rank <= 1
                                                    AND gss_ranked_by_time.time >= now() - interval '24 hours')
GROUP BY game_server_address;
