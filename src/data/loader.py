"""Load player projections from CSV files."""

import pandas as pd
from pathlib import Path
from typing import Dict

from ..models.player import PlayerProjection, Position


# Name normalization mappings
NAME_ALIASES = {
    "Devonta Smith": "DeVonta Smith",
    "D'Andre Swift": "D'Andre Swift",
    "Travis Etienne Jr.": "Travis Etienne Jr.",
}

# Team abbreviation normalization
TEAM_ALIASES = {
    "JAC": "JAX",
    "JAX": "JAX",
    "LA": "LAR",
    "LAR": "LAR",
}


def normalize_team(team: str) -> str:
    """Normalize team abbreviation."""
    return TEAM_ALIASES.get(team, team)


def load_skill_projections(filepath: str) -> Dict[str, PlayerProjection]:
    """
    Load RB/WR/TE projections from CSV.

    CSV format: Player,Team,POS,ATT,YDS,TDS,REC,YDS,TDS,FL,FPTS
    (YDS and TDS columns are duplicated - first is rushing, second is receiving)
    """
    df = pd.read_csv(filepath, header=0)

    # Rename duplicate columns
    new_cols = ['Player', 'Team', 'POS', 'RUSH_ATT', 'RUSH_YDS', 'RUSH_TDS',
                'REC', 'REC_YDS', 'REC_TDS', 'FL', 'FPTS']
    df.columns = new_cols

    # Extract base position
    df['POS_BASE'] = df['POS'].str.extract(r'([A-Z]+)')

    projections = {}
    for _, row in df.iterrows():
        pos_str = row['POS_BASE']
        try:
            pos = Position(pos_str)
        except ValueError:
            continue  # Skip unknown positions

        team = normalize_team(row['Team'])
        proj = PlayerProjection(
            name=row['Player'],
            team=team,
            position=pos,
            rush_att=float(row['RUSH_ATT']),
            rush_yds=float(row['RUSH_YDS']),
            rush_tds=float(row['RUSH_TDS']),
            rec=float(row['REC']),
            rec_yds=float(row['REC_YDS']),
            rec_tds=float(row['REC_TDS']),
            fumbles_lost=float(row['FL']),
        )
        # Store under original name
        projections[row['Player']] = proj

        # Also store under common name variants
        for variant, canonical in NAME_ALIASES.items():
            if row['Player'] == canonical:
                projections[variant] = proj
            elif row['Player'] == variant:
                projections[canonical] = proj

    return projections


def load_qb_projections(filepath: str) -> Dict[str, PlayerProjection]:
    """
    Load QB projections from CSV.

    CSV format: Player,Team,ATT,CMP,YDS,TDS,INTS,ATT,YDS,TDS,FL,FPTS
    (ATT, YDS, TDS duplicated - first is passing, second is rushing)
    """
    # Skip the empty row 2
    df = pd.read_csv(filepath, header=0, skiprows=[1])

    # Remove empty rows
    df = df.dropna(how='all')
    df = df[df['Player'].str.strip() != '']

    # Rename columns
    new_cols = ['Player', 'Team', 'PASS_ATT', 'PASS_CMP', 'PASS_YDS', 'PASS_TDS',
                'INTS', 'RUSH_ATT', 'RUSH_YDS', 'RUSH_TDS', 'FL', 'FPTS']
    df.columns = new_cols

    # Convert to numeric
    for col in df.columns[2:]:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    projections = {}
    for _, row in df.iterrows():
        team = normalize_team(row['Team'])
        proj = PlayerProjection(
            name=row['Player'],
            team=team,
            position=Position.QB,
            pass_att=float(row['PASS_ATT']),
            pass_cmp=float(row['PASS_CMP']),
            pass_yds=float(row['PASS_YDS']),
            pass_tds=float(row['PASS_TDS']),
            ints=float(row['INTS']),
            rush_att=float(row['RUSH_ATT']),
            rush_yds=float(row['RUSH_YDS']),
            rush_tds=float(row['RUSH_TDS']),
            fumbles_lost=float(row['FL']),
        )
        projections[row['Player']] = proj

    return projections


def load_all_projections(
    skill_path: str = None,
    qb_path: str = None
) -> Dict[str, PlayerProjection]:
    """Load all projections from default or specified paths."""
    # Try local data folder first, then Dropbox
    project_dir = Path(__file__).parent.parent.parent / "data"
    dropbox_dir = Path.home() / "Dropbox" / "fantasy-wc"

    if skill_path is None:
        local_skill = project_dir / "fantasy-wc-2026.csv"
        skill_path = local_skill if local_skill.exists() else dropbox_dir / "fantasy-wc-2026.csv"
    if qb_path is None:
        local_qb = project_dir / "fantasy-wc-QB-2026.csv"
        qb_path = local_qb if local_qb.exists() else dropbox_dir / "fantasy-wc-QB-2026.csv"

    projections = {}
    projections.update(load_skill_projections(str(skill_path)))
    projections.update(load_qb_projections(str(qb_path)))

    return projections
