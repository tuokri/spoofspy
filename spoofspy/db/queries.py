from pathlib import Path

from sqlalchemy import text

# TODO: is there a better way to make this available in multiple places?
trust_aggregate = text((Path(__file__).parent / "trust_aggregate.sql").read_text())
