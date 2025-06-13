# MetGenC Architecture

## Runtime Behavior

```mermaid
%%{init: {
  'theme': 'base',
  'themeVariables': {
    'fontSize': '14px',
    'fontFamily': 'arial',
    'primaryColor': '#E8E8E8',
    'primaryTextColor': '#000000',
    'primaryBorderColor': '#404040',
    'lineColor': '#303030',
    'secondaryColor': '#D0D0D0',
    'tertiaryColor': '#B8B8B8',
    'backgroundColor': '#F8F8F8'
  }
}}%%

graph TB
    subgraph Runtime["Runtime Behavior"]
        subgraph Inputs["Input Sources"]
            CF[NetCDF Files]
            INI[".ini Config File"]
            AWS[AWS Credentials]
            EDL[Earthdata Login]
            PRE["Premet Files <br>(optional)"]
            SPA["Spatial Files <br>(optional)"]
            style Inputs fill:#F0F0F0,stroke:#404040
        end

        subgraph Processing["Processing Pipeline"]
            READ[Read Files]
            VAL[Validate Inputs]
            META[Extract Metadata]
            GEN[Generate UMM-G]
            CNM[Create CNM Message]
            style Processing fill:#F0F0F0,stroke:#404040
        end

        subgraph Outputs["Output Results"]
            UMMG["UMM-G Files<br>(local + S3)"]
            CNMF["CNM Files<br>(local, optional)"]
            S3["Data Files in S3"]
            KIN["Kinesis Messages"]
            style Outputs fill:#F0F0F0,stroke:#404040
        end

        CF --> READ
        INI --> READ
        AWS --> READ
        EDL --> READ
        PRE --> READ
        SPA --> READ

        READ --> VAL
        VAL --> META
        META --> GEN
        GEN --> CNM

        GEN --> UMMG
        CNM --> CNMF
        CF --> S3
        CNM --> KIN

        style Runtime fill:#FFFFFF,stroke:#404040
    end
```

## Code Structure and Processing Flow

```mermaid
%%{init: {
  'theme': 'base',
  'themeVariables': {
    'fontSize': '14px',
    'fontFamily': 'arial',
    'primaryColor': '#E8E8E8',
    'primaryTextColor': '#000000',
    'primaryBorderColor': '#404040',
    'lineColor': '#303030',
    'secondaryColor': '#D0D0D0',
    'tertiaryColor': '#B8B8B8',
    'backgroundColor': '#F4F4F4'
  }
}}%%

graph TB
    subgraph Architecture["MetGenC Architecture"]
        subgraph CLI["CLI Layer"]
            direction TB
            CLI_CMD["cli.py<br>(Click Commands)"]
            CONF["config.py<br>(INI Parser)"]
            style CLI fill:#F0F0F0,stroke:#404040
        end

        subgraph DAL["Data Access Layer"]
            direction TB
            NET["NetCDFReader<br>(xarray)"]
            CSV["CSVReader"]
            SNOW["SnowExCSVReader"]
            AWS["aws.py<br>(S3/Kinesis)"]
            CMR["cmr.py<br>(EDL Auth)"]
            style DAL fill:#F0F0F0,stroke:#404040
        end

        subgraph PROC["Processing Layer"]
            direction TB
            MET["metgen.py<br>(Orchestration)"]
            PROCESSOR["processor.py<br>(Data Processing)"]
            TEMP["templates/<br>(Jinja2)"]
            VALID["validator.py<br>(JSON Schema)"]
            style PROC fill:#F0F0F0,stroke:#404040
        end

        subgraph OUT["Output Layer"]
            direction TB
            UMMG_GEN["UMM-G Generator"]
            CNM_GEN["CNM Generator"]
            S3_UP["S3 Uploader"]
            KIN_PUB["Kinesis Publisher"]
            style OUT fill:#F0F0F0,stroke:#404040
        end

        CLI_CMD --> CONF
        CONF --> MET

        MET --> NET
        MET --> CSV
        MET --> SNOW
        MET --> AWS
        MET --> CMR

        MET --> PROCESSOR
        PROCESSOR --> TEMP
        PROCESSOR --> VALID

        PROCESSOR --> UMMG_GEN
        PROCESSOR --> CNM_GEN
        UMMG_GEN --> S3_UP
        CNM_GEN --> KIN_PUB

        style Architecture fill:#FFFFFF,stroke:#404040
    end
```

### Diagram Legend

1. Runtime Behavior shows:
- Input dependencies (data files, config, credentials)
- Main processing steps
- Output artifacts and side effects
- Optional components

2. Code Structure shows:
- Layered architecture (CLI, Data Access, Processing, Output)
- Component responsibilities and relationships
- Data flow between components
- Integration points with external services
- Key classes and modules

Color coding in Code Structure diagram:
- Light Grey (#E8E8E8): Entry points/CLI layer
- Medium Light Grey (#D0D0D0): Core processing components
- Medium Grey (#B8B8B8): External service integrations
- Dark Grey (#A0A0A0): Output generators
