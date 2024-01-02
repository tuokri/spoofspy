# spoofspy

Experimental app for detecting and displaying spoofed/redirect servers on Steam.

Calculates a trust score based on multiple criteria to determine
a rolling average that indicates which servers are trustworthy i.e.
real servers vs. fake severs with low trust score that often have spoofed
information such as player counts.

Trust score evaluation currently supported on the following games:

- Rising Storm 2: Vietnam

## Technical details

The backend core is implemented as multiple Celery jobs and a
PostgreSQL+TimescaleDB cluster that perform the following actions:

1. A periodic job request Steam Web API
   [(IGameServersService/GetServerList)](https://steamapi.xpaw.me/#IGameServersService/GetServerList)
   for a list of dedicated servers
   based on some query criteria stored in the database. The result of this
   query is stored in the database.
2. For each server discovered, an individual Celery job is started to
   perform A2S_INFO, A2S_RULES and A2S_PLAYERS queries. The results of these
   queries are stored in the database as timeseries.
3. A periodic Celery job calculates the trust scores for the servers
   based on the above queries. The heuristic trust score algorithm details
   can be seen [here](spoofspy/heuristics/trust.py).

Data model defined in detail for Timescale
[here](spoofspy/db/timescale.sql) and for SQLAlchemy
[here](spoofspy/db/models.py).

## Future improvements

- Public web GUI
    - Currently only has backend functionality
      and private APIs for development and testing

## TODO

- Import `_version.py` to make it available in releases.
    - Actually, consider if we want to do this? There seem to
      be many opinions on whether having a __version__ attribute
      is the right way to do it.

# License

```
Copyright (C) 2023-2024  Tuomo Kriikkula
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
```
