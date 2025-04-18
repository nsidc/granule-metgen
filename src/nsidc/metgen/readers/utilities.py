from datetime import timezone

from dateutil.parser import parse


def temporal_from_premet(premet_path: str) -> list:
    if premet_path == "":
        raise Exception(
            "premet_dir is specified but no premet file exists for granule."
        )

    pdict = premet_values(premet_path)
    begin = " ".join([pdict["RangeBeginningDate"], pdict["RangeBeginningTime"]])
    end = " ".join([pdict["RangeEndingDate"], pdict["RangeEndingTime"]])
    return [ensure_iso(begin), ensure_iso(end)]


def premet_values(premet_path: str) -> dict:
    pdict = {}
    with open(premet_path) as premet_file:
        for line in premet_file:
            key, val = line.strip().split("=")
            pdict[key] = val

    return pdict


def ensure_iso(datetime_str):
    """
    Parse ISO-standard datetime strings without a timezone identifier.
    """
    iso_obj = parse(datetime_str)
    return format(iso_obj)


def format(iso_obj):
    return (
        iso_obj.replace(tzinfo=timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )
