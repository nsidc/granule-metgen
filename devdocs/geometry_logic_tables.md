# Inputs

## Sources

* Collection metadata [CM]
* Science file [SCI]
* SPO file [SPO]
* Spatial file [SPA]

## GSRCS

* Geodetic [GEO]
* Cartesian [CAR]

## Configuration Directive

* Collection geometry override (default false) [CGO]

# Output

## Types

* None/Error [ø]
* Point [PNT]
* BoundingBox [BBX]
* Polygon [PGN]

# Rules

## Preconditions

IF CGO==TRUE ==> BBOX(CM)

IF CSMG==CAR & #BR==1 & GSRCS=GEO ==> ø
IF CSMG==CAR & #BR==1 & GSRCS=CAR ==> BBOX(CM)
IF CSMG==CAR & #BR>=2             ==> ø

## Rules

| SPO | SPA | SCI | GSRCS | # POINTS: 0 | # POINTS: 1 | # POINTS: 2 | # POINTS: >2 | Notes           |
|-----|-----|-----|-------|-------------|-------------|-------------|--------------|-----------------|
|  F  |  F  |  F  | GEO   |      ø      |      ø      |      ø      |      ø       |                 |
|  F  |  F  |  F  | CAR   |      ø      |      ø      |      ø      |      ø       |                 |
|  F  |  F  |  T  | GEO   |      ø      |     PGN     |      ø      |     PGN      | From data       |
|  F  |  F  |  T  | CAR   |      ø      |      ø      |     BBX     |      ø       | From metadata   |
|  F  |  T  |  F  | GEO   |      ø      |     PNT     |     PGN     |     PGN      |                 |
|  F  |  T  |  F  | CAR   |      ø      |      ø      |     BBX     |      ø       |                 |
|  F  |  T  |  T  | GEO   |             |             |             |              | Priority ?      |
|  F  |  T  |  T  | CAR   |             |             |             |              | Priority ?      |
|  T  |  F  |  F  | GEO   |      ø      |      ø      |      ø      |     PGN      |                 |
|  T  |  F  |  F  | CAR   |      ø      |      ø      |      ø      |      ø       |                 |
|  T  |  F  |  T  | GEO   |             |             |             |              | Priority ?      |
|  T  |  F  |  T  | CAR   |             |             |             |              | Priority ?      |
|  T  |  T  |  F  | GEO   |             |             |             |              | Priority ?      |
|  T  |  T  |  F  | CAR   |             |             |             |              | Priority ?      |
|  T  |  T  |  T  | GEO   |             |             |             |              | Priority ?      |
|  T  |  T  |  T  | CAR   |             |             |             |              | Priority ?      |
