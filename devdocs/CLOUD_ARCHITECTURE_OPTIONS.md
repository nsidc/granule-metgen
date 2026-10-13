# Cloud-ifying MetGenC — Architecture Options and FY27 Scope

**Status:** Revised 2026-10-13 following the 2026-09-14 stakeholder meeting. Supersedes the
reconnaissance draft for [issue #341](https://github.com/nsidc/granule-metgen/issues/341)
(`1f5c267`).
**Baseline:** MetGenC v1.16.0 (`bf5abd5`)

This document has two parts:

- **Part I — Decision brief (§1)** is for DAAC management and the MetGenC product owner. It is
  the basis for deciding the FY27 funding level.
- **Part II — Technical detail (§2–§8)** is for the MetGenC project team. It holds the evidence
  behind Part I and the work breakdown.

No prototype was built. Where Part II asserts a fact about the codebase it cites `file:line`;
where it asserts AWS behaviour that has not been tested here, it says so. Prices are AWS
us-west-2 list prices as of October 2026 and should be re-checked before being quoted.

---

# Part I — Decision brief

## 1. The decision

Earthdatapub CUE will deliver data to NSIDC in **provider-owned S3 buckets, in AWS accounts
other than NSIDC's**. MetGenC today can only read files from a local disk. DAAC management is
asked to choose how far FY27 goes in closing that gap:

- **Option A — run today's MetGenC, unchanged, on an EC2 instance in AWS.** Something other than
  MetGenC brings the data to it: either a copy onto the instance's disk (**A1**), or a mount that
  makes the provider's bucket look like a local directory (**A2**).
- **Option B — make MetGenC read from S3 itself.** Everything in Option A, plus code changes so
  that MetGenC lists, reads, and stages data in S3 directly.

**Recommendation: fund Option B.** Option A works, and is an acceptable fallback if funding allows
nothing more, but it is sub-optimal for the reasons in §1.3. All of Option A's work is reused by
Option B, so funding A now does not foreclose B later.

### 1.1 Requirements

Agreed at the 2026-09-14 meeting (Troy, Kara, Lisa K, Lauren, Julia, Kevin):

| Requirement | |
|---|---|
| Read source data from a provider-owned S3 bucket in a different AWS account from NSIDC's destination (CUE) | **Must** |
| Operator-driven runs, as today | **Must** |
| One codebase that also keeps the on-prem workflow working, indefinitely | **Must** |
| Run on EC2, built from the NGAP AMI with Terraform | **Must** |
| Logs streamable to CloudWatch so that alerts can be created | **Must** |
| Event-driven (unattended) runs | Nice to have |
| Container image | Only if clearly better — it is not, for FY27 (§4.6) |
| netCDF-3 files | Never needed |

I&A will build nothing that affects MetGenC; its plans do not constrain this scope.

### 1.2 Options compared

| | **A1 — EC2 + copy** | **A2 — EC2 + mount** | **B — S3-native MetGenC** |
|---|---|---|---|
| How data reaches MetGenC | Operator copies it from the provider bucket to the instance's disk, then runs MetGenC | Provider bucket is mounted read-only; MetGenC reads it as ordinary files | MetGenC reads the provider bucket directly |
| MetGenC code changes | None | None | Yes |
| Meets the CUE requirement | By workaround — a copy tool reads S3, not MetGenC | By workaround — the mount reads S3, not MetGenC | Yes |
| Extra operator work per run | Copy, size the disk, clean up | None once mounted | None |
| Proven? | Yes — the spring 2026 EC2 experiment | No — needs a short trial | No — needs development |
| Times each data file crosses the network | 2 | 3 | 0 – 2 |
| Moves MetGenC toward unattended runs | No | No | Partly |
| Relative effort (§6) | One M and five S tasks | Same as A1 | A, plus one L and three to four M |

### 1.3 Why Option A is sub-optimal, and what it actually costs

**A correction to the earlier draft.** The earlier draft said Option A leaves the data-egress cost
unsolved. That was wrong.

- **Today**, data already in S3 is copied to the on-prem host `nusnow`, paid for as S3 internet
  egress: about $0.09 per GB, or ~$90 per TB.
- **All three options run in us-west-2**, the same region as the provider buckets, and AWS does not
  charge for moving data between S3 and EC2 within a region. **Every option removes today's
  egress charge** — provided the instance reaches S3 through an S3 *gateway endpoint*.
- **If the NGAP network instead routes S3 traffic through a NAT gateway**, every gigabyte crossing
  the instance costs about $0.045. Option A moves each file across the network two or three
  times, so it would then cost **about as much as today's egress, or more** (~$90–135 per TB),
  against ~$0–90 per TB for Option B. Which routing NGAP uses is not yet known. It is the fact most
  likely to change the dollar comparison, and if it is NAT, the fix is a network configuration
  change rather than MetGenC work.

Option A's shortfall is therefore mainly **operational**:

- **A1** copies every granule in full before processing. The operator must run the copy with the
  provider's credentials, size the disk for the batch, and clean up afterwards. Every run waits for
  the copy.
- **A2** removes the copy step and the disk sizing, but it is untried on the NGAP AMI, and it
  reads every file in full at least twice through the mount.
- **Neither** can have S3 perform the copy to NSIDC's bucket server-side, and neither moves
  MetGenC any closer to unattended operation.

### 1.4 Open items — none block this decision

| Unknown | Effect |
|---|---|
| How each provider grants access: a bucket policy naming NSIDC, or NSIDC assuming a role in the provider's account | Both are planned for. It determines how much of Option B's data-movement saving is realized. |
| Whether the NGAP network reaches S3 through a gateway endpoint or NAT | Decides the dollar comparison in §1.3. |
| Where operator-supplied premet/spatial files will live in the cloud | Option B handles any answer; Option A needs a runbook decision. |
| Whether the S3 mount works on the NGAP AMI | Decides only between A1 and A2. |

---

# Part II — Technical detail

## 2. Drivers and constraints

### 2.1 Drivers

1. **Earthdatapub CUE.** CUE is a mechanism by which a data provider supplies NSIDC's source data
   in an S3 bucket the provider owns. That bucket will usually be in a different AWS account from
   NSIDC's destination — the Cumulus staging bucket and Kinesis stream — with different
   authentication and authorization. MetGenC must read from the source and stage data and metadata
   to the destination. CUE delivers data; it does not invoke MetGenC, so it imposes no invocation
   contract.
2. **Cost.** Processing S3-resident data on-prem means first copying it out of AWS over the
   internet (§5).
3. **Enterprise reach.** Suzanne's spring experiment processed one granule on one NSIDC EC2
   instance. Stakeholders called that "bare minimum with some heavy lifting".
4. **Funding uncertainty.** It is genuinely uncertain whether FY27 funding will cover more than
   Option A, so this document specifies Option A fully rather than as a strawman.

### 2.2 Constraints

| # | Constraint | Source | Consequence |
|---|---|---|---|
| C1 | One codebase keeps supporting the on-prem VM workflow **indefinitely**. How long the transition to all-cloud will take is unknown. | Amy Fitz's original question; confirmed 2026-09-14 | Rules out a cloud fork. Any S3 support sits behind an interface that also resolves local paths. |
| C2 | Operator-driven invocation is required. Event-driven invocation is a nice-to-have. | 2026-09-14 | FY27 design may assume a human runs MetGenC with an `.ini`, but must not foreclose unattended runs (§4.6). |
| C3 | Must run on EC2 in the mediation account, us-west-2, built from the NGAP AMI with Terraform. A container is optional. On-prem does not use Docker. | 2026-09-14; Kevin | The deliverable is the pip-installed package, on both the VM and EC2. |
| C4 | Source buckets are provider-owned, in another account, and likely in us-west-2. The access model per provider is unknown. The destination S3 bucket and Kinesis stream are reached with one identity. | 2026-09-14; Kevin | Plan for both source access models (§4.5). |
| C5 | Logs must be streamable to CloudWatch so that alerts can be created. | 2026-09-14 | Met on EC2 without code change (§3.2, seam 6). |
| C6 | netCDF-3 never needs to be read. | 2026-09-14; Kevin | Byte-range netCDF reads are available for every netCDF file (§3.3). |

Both standing unknowns from the earlier draft are resolved: what CUE requires (driver 1), and what
I&A will build (nothing affecting MetGenC).

---

## 3. Where MetGenC is today

### 3.1 Current deployment model

MetGenC is a `pip`-installed CLI run interactively by a human on a long-lived NSIDC VM:

```
vssh production metgenc
cd metgenc; source .venv/bin/activate
source metgenc-env.sh cumulus-uat     # or cumulus-prod
metgenc process -c my_collection.ini
```

- Data is staged on NFS (`/disks/sidads_staging/...`); logs are written to `/share/logs/metgenc`.
- AWS credentials are **static long-lived keys** read from a named profile in `~/.aws/credentials`
  and exported into the environment by `scripts/metgenc-env.sh:11-19`.
- Earthdata Login credentials come from `EARTHDATA_USERNAME` / `EARTHDATA_PASSWORD` in the
  environment, set on the VM by `/etc/profile.d/metgenc-init.sh`.
- There is **no Dockerfile, no container image, and no infrastructure-as-code** anywhere in the
  repository. CI (`.github/workflows/build-test.yml`) runs lint and unit tests only;
  `publish.yml` builds a wheel and publishes to PyPI on release.

### 3.2 The porting surface: six seams

MetGenC's coupling to the local filesystem is **small and well-localized**: about a dozen call sites
in six places. Under Option B, FY27 ports only the input side; outputs and logs stay on the EC2
instance's local disk.

| # | Seam | Call sites | Under Option B |
|---|---|---|---|
| 1 | **Listing** (granule discovery) | `metgen.py:500` — `[p for p in Path(configuration.data_dir).glob("*")]`<br>`metgen.py:523-537` — `ancillary_files()`, same pattern for premet/spatial dirs | **Ported.** `Path().glob("*")` is non-recursive and **eager**: it materializes the whole listing before the lazy per-granule generator (`599cb7b`) engages. The S3 lister must paginate. |
| 2 | **Reading bytes** | `readers/netcdf_reader.py:36` — `Dataset(netcdf_path)`<br>`readers/utilities.py:73` — `open(premet_path)`<br>`readers/utilities.py:331` — `open(spatial_path)` | **Ported.** Premet and spatial files are small text files: a whole-object GET. netCDF is the hard one — §3.3. |
| 3 | **Stat and checksum** | `metgen.py:301-305` — `os.path.getsize()` in `Granule.size()`<br>`metgen.py:986` — `os.path.getsize(file)`<br>`metgen.py:1017-1027` — `checksum()`, streaming SHA-256 over `open(file, "rb")` | **Ported.** Size comes free with the listing. The checksum is less simple than the earlier draft claimed — §3.4. |
| 4 | **Writing outputs** | `config.py:76-80` — `ummg_path()` / `cnm_path()`, pure `Path` joins<br>`metgen.py:835` — UMM-G write<br>`metgen.py:915` — CNM write<br>`metgen.py:1179` — `output_file_path.glob("*.json")` in `validate()`<br>`metgen.py:1222` — `open(json_file)` in `apply_schema()` | **Not ported.** UMM-G and CNM files stay on the instance's local disk before staging. Note `metgen.py:337`: `# TODO: Do any prep actions, like mkdir, etc` — output directories must pre-exist. |
| 5 | **Staging to S3** | `metgen.py:841-854` — `open(fn, "rb")` then `aws.stage_file(...)` → `aws.py:67` `upload_fileobj` | **Ported.** Becomes a server-side copy or a single streamed pass, depending on the access case (§4.5). |
| 6 | **Logging** | `constants.py:28` — `DEFAULT_LOG_DIR = "/share/logs/metgenc"`<br>`metgen.py:67-83` — `os.path.join(log_dir, ...)` → `logging.FileHandler(log_path, "a")`<br>`config.py:448-456` — validates the dir exists **and** is writable | **Not ported.** `log_dir` is already an `.ini` setting (`config.py:56`). On EC2, point it at a local directory and let the CloudWatch agent ship the file to CloudWatch Logs — this meets C5 with no code change. A stdout sink is only needed for a container, which is deferred (§4.6). |

### 3.3 The netCDF reader

`netCDF4.Dataset` (`readers/netcdf_reader.py:36`) cannot open an `s3://` path. The reader never
reads bulk science data — only global attributes and the coordinate variables it needs for temporal
and spatial coverage — so for a large granule the bytes it needs are a small fraction of the file.

The earlier draft left open whether byte-range reads were possible, because netCDF-3 classic files
cannot be read that way. With netCDF-3 out of scope (C6), every netCDF file is netCDF-4/HDF5 and
byte-range reads are always available. The open choice is now only *which route*:

| Route | How | Trade-off |
|---|---|---|
| **fsspec** | `xarray` / `h5netcdf` over an `s3fs` file object | Least code. `s3fs` depends on `aiobotocore`, which pins `botocore` narrowly and can conflict with the `boto3` that `aws.py` uses (R3). |
| **boto3 range reader** | `h5netcdf` — whose `legacyapi` mirrors the `netCDF4` API the reader already uses — over a small seekable file object that issues ranged `GetObject` calls | No new heavy dependency, and the same credentials as the rest of MetGenC; a small amount of code to own. |
| **Mount** (Option A2 only) | `netCDF4.Dataset` on a path under a Mountpoint mount | No code at all. The mount turns HDF5's reads into ranged GETs. |

`xarray` is already a declared dependency (`pyproject.toml:17`), though unused in production code.
W8 chooses between the first two routes by measuring both on a representative large granule.

Two secondary observations on this file:

- The `Dataset` handle at `netcdf_reader.py:36` is **never closed** — there is no context manager.
  Harmless in a short CLI run; a file-descriptor or connection leak in a long-running cloud
  process.
- Reader dispatch is by local file suffix (`readers/registry.py:16-20`, via `metgen.py:472-490`).
  Only `.nc` maps to a real reader; everything else falls through to `generic.extract_metadata`,
  which **never opens the data file at all** (`readers/generic.py:7-34`). So CSV/TXT/JPEG
  collections need no data-file read — seam 2 only bites for netCDF collections.

### 3.4 Facts that change the cost of the port

- **`aws.py` needs no change for the destination; the source depends on the access case.** All four
  boto3 clients (`aws.py:17`, `:29`, `:44`, `:56`) are bare `boto3.client(...)` calls on the
  **default credential chain**. Because the destination S3 bucket and Kinesis stream share one
  identity (C4), an instance profile, or an `AWS_PROFILE` that assumes the #302 role, works with no
  code change. Reading the source with the same clients works only if that same identity can read
  the provider's bucket; otherwise `aws.py` needs a session per location (§4.5). The earlier draft
  stated the no-change claim unconditionally; that was too strong. The operator-workflow point
  stands: `scripts/metgenc-env.sh` exports static keys scraped from a named profile, and retiring
  that is what #302 is really about.
- **EDL auth is one line.** `collection_metadata.py:69-71` hardcodes
  `earthaccess.login(strategy="environment", ...)`. Injecting the same environment variables from
  Secrets Manager or SSM Parameter Store at login satisfies #303 with no code change. The
  hardcoded strategy also means `.netrc` and interactive login are unreachable today, despite what
  the earthaccess error message advertises.
- **Checksums are harder to get from S3 than the earlier draft claimed.** CNM accepts only
  `SHA512`, `SHA256`, `SHA2`, `SHA1`, or `md5` (`json-schema/cumulus_sns_schema.json:33-38`), and
  MetGenC hardcodes SHA-256 (`metgen.py:1017-1027`, `templates/cnm_files_template.txt:5`).
  - S3's default object checksum is CRC-64/NVME, which CNM does not accept.
  - A SHA-256 exists on a provider's object only if the provider requested one at upload, and for
    a multipart upload it is a checksum of part checksums, not of the file.
  - So `head_object` cannot be relied on. What can be: requesting `ChecksumAlgorithm=SHA256` on a
    server-side `copy_object`, which makes S3 compute the SHA-256 of the destination object without
    the bytes leaving S3.
  - A single `copy_object` is limited to 5 GB. Larger objects need a multipart copy, whose checksum
    is again composite, so files over 5 GB must be read once to hash.

  *Not tested here — W9 verifies this against real S3 before relying on it.*
- **Staging can become a server-side copy — when one identity spans source and destination.** A
  `copy_object` is a single request signed by one identity, which must be able to read the source
  and write the destination. In that case the bytes never pass through MetGenC. Otherwise staging
  is a single streamed pass that hashes while it uploads.
- **There is prior art to build on.** `devdocs/PIPELINE_REFACTORING_PLAN.md:270` sketches the
  pipeline steps `CreateUMMG, CreateCNM, WriteFile, S3Upload, SendMessage`, and
  `tests/integration/configs/IRWIS2DUCk.ini:10-12` carries a commented-out `[Pipeline]` section.
  The deferred event-driven work (§4.6) continues that thinking.

### 3.5 Configuration

`config.py:87` requires the `.ini` to be an existing local file, and `validate()`
(`config.py:376-396`) requires `os.path.exists()` on `data_dir`, `premet_dir`, `spatial_dir`, and
`local_output_dir`. Under operator-driven invocation (C2) a local `.ini` on the EC2 instance is
fine. Option B relaxes the existence checks for `s3://` locations.

There are **no auth keys of any kind in the `.ini`** — no EDL credentials, no AWS profile, no
region, no role ARN. All authentication is ambient environment. That is a good property to
preserve. In the two-identity case (§4.5) the `.ini` would need to *name* the AWS profile or role to
use for the source location. A profile name or role ARN is not a secret, so the property holds.

Two incidental defects, worth fixing whenever those files are next touched but not part of this
scope: `checksum_type` is parsed into `Config` but never read (SHA-256 is hardcoded, above), and
`date_modified` in `tests/integration/configs/IPFLT1B_DUCk.ini:13` is not a recognized key and is
silently ignored.

---

## 4. Options in detail

The options are **nested**: A1 and A2 are alternative ways of getting data onto the same EC2 host,
and Option B is that host plus code changes that make A1/A2's input step unnecessary. Everything
in §4.1 is shared.

### 4.1 Common to every option: the EC2 host

- An EC2 instance in the mediation account, us-west-2, built from the NGAP AMI and provisioned with
  Terraform.
- MetGenC installed with `pip` — the same package the on-prem VM uses.
- **Destination identity** (#302): one identity writes the Cumulus staging bucket and posts to
  Kinesis, via the instance profile or an `AWS_PROFILE` that assumes the cross-account role. Static
  keys and `metgenc-env.sh` are retired for cloud use. No MetGenC code change (§3.4).
- **Source access** (#301): per provider, one of the two cases in §4.5.
- **EDL credentials** (#303): from Secrets Manager or SSM Parameter Store into `EARTHDATA_*` at
  login. No code change.
- **Logging**: `log_dir` in the `.ini` points at a local directory; the CloudWatch agent ships it to
  CloudWatch Logs; metric filters and alarms trigger on error lines. No code change.

### 4.2 Option A1 — EC2 + copy

**What changes.** No MetGenC code. Per run, the operator:

1. Copies the provider's data to the instance with `aws s3 sync s3://<provider-bucket>/<prefix>
   /data/<run>`, using the source credentials.
2. Runs `metgenc process` with `data_dir` pointing at the local copy.
3. Deletes the local copy.

**What it buys.** It is the proven pattern — essentially Suzanne's experiment — and it needs nothing
new. It handles the two-identity case naturally, because the copy tool uses the source credentials
and MetGenC uses the destination credentials.

**What it costs.**

- A full copy before every run, so every run waits for it.
- An EBS volume sized for the largest batch.
- Manual cleanup.
- Each data file crosses the network twice: copied in, uploaded out (§5.2).
- The operator handles a second set of credentials.

### 4.3 Option A2 — EC2 + mount

**What changes.** No MetGenC code. The provider's bucket is mounted read-only with Mountpoint for
Amazon S3 (`mount-s3`), AWS's open-source FUSE client, using `--read-only` and the source
credentials (`--profile`). `data_dir` points into the mount.

How MetGenC's seams behave over the mount:

- Listing (seam 1) becomes `ListObjectsV2` calls.
- `os.path.getsize` (seam 3) is answered from listing metadata.
- `netCDF4.Dataset` (seam 2) issues ranged GETs, so only the attributes and coordinate variables
  cross the network.
- The checksum (seam 3) and staging (seam 5) still read every byte through the mount.

**What it buys.** No copy step, and no disk to size. Like A1, it handles two identities naturally,
because the mount holds the source credentials.

**What it costs, and what is unknown.**

- It is **untried**: FUSE and `mount-s3` must be permitted on the NGAP AMI.
- Each data file crosses the network three times: read for the checksum, read again for staging,
  then uploaded out. Mountpoint's optional local cache would cut that to two, at the price of
  reintroducing disk sizing.
- HDF5's small random reads over S3 latency may be slow; nobody has measured it.
- Someone owns the mount's lifecycle: who mounts it, and remounting after a reboot.

A short spike (W6b) settles A2 against A1.

### 4.4 Option B — S3-native MetGenC (recommended)

**What changes.**

1. **A storage interface for input locations.** Each of `data_dir`, `premet_dir`, and `spatial_dir`
   accepts either a local path or an `s3://` URI. Seams 1, 2, 3, and 5 route through it. Each
   location resolves independently, so one run can combine provider S3 data with operator-supplied
   premet/spatial files wherever those end up (N3).
2. **netCDF reads by byte range** (§3.3).
3. **S3-native staging and checksums.** A server-side copy with an S3-computed SHA-256 when one
   identity spans source and destination; otherwise one streamed pass that hashes while it uploads
   (§3.4).
4. **Per-location credentials**, only if some provider needs two identities (§4.5).

**What does not change:**

- the CLI and the `.ini` format, which gains only new optional keys;
- the operator workflow — an `s3://` URI goes where a path used to;
- outputs and logs, which stay on local disk;
- the deployment — the same `pip` package on the same EC2 host.

An operator on the on-prem VM keeps typing exactly what they type today, with local paths, and it
keeps working. **This is what satisfies C1** — the same interface that enables S3 preserves on-prem.

**What it buys.**

- No copy step, no disk sizing, and no mount.
- The least data movement of any option, with zero passes through the instance when one identity
  spans both accounts (§5.2).
- It meets the CUE requirement as stated — MetGenC itself reads the provider bucket.
- It removes MetGenC's filesystem dependency, which is a prerequisite for any later event-driven
  operation.

**What it costs.** One L and three to four M workstreams (§6.2), including test churn: the unit
tests build real `tmp_path` directories and pass `Path` objects directly into the grouping functions
(`tests/test_metgen.py:107-115` and many call sites).

**What could invalidate it.** Nothing currently known. The earlier draft's one contingency — I&A
superseding the work — is resolved.

### 4.5 Source-account access: two cases

How a provider grants NSIDC access to its bucket is not yet known and may differ by provider (N1).
Both cases are planned for.

**Case 1 — the provider's bucket policy grants read access to an NSIDC principal.**

- **1a: the grant names the destination identity.** One identity reads the source and writes the
  destination. `aws.py` is unchanged; server-side copy is available; staging moves no bytes through
  the instance.
- **1b: the grant names some other NSIDC principal** (for example the instance role, when the
  destination is reached through an assumed role). In practice this is two identities: see Case 2.

**Case 2 — NSIDC assumes a role in the provider's account.** Two identities are in play.

- `aws.py` must hold one boto3 session per location; today it uses only the default session.
- Server-side copy is impossible, because no single identity can both read the source and write
  the destination.
- Staging becomes one streamed pass, GET from the source and PUT to the destination, hashing as it
  goes.

**Recommendation for provider onboarding:** ask for Case 1a — a bucket-policy grant to the
destination identity. It is the only configuration that delivers Option B's full benefit, and it
costs the provider nothing more than any other grant.

**Effect on Option A:** none. A1 and A2 split the credentials across tools — the copy or mount uses
the source credentials, and MetGenC uses the destination credentials.

**Encryption.** SSE-KMS with provider-managed keys did not come up. If any provider uses it, the
key policy must also grant decrypt to the reading identity (N6).

### 4.6 Deferred: container and event-driven invocation (formerly Option C)

The earlier draft's Option C existed because CUE might have required an invocable service. CUE
turns out to be a data-delivery mechanism (§2.1), so that reason is gone. What remains is
event-driven operation, which is a nice-to-have (C2).

**Container — deferred.** By the criteria that matter for FY27, a container is not clearly better:

1. On-prem does not use Docker, so the `pip` package is required anyway (C1). A container would be
   a second deliverable, not a replacement.
2. EC2 built from the NGAP AMI is the required target (C3), and a `pip` install works there just as
   it does on the VM.
3. The native-dependency argument is weaker than the earlier draft claimed. MetGenC has no direct
   GDAL dependency, and `netCDF4` and `geopandas` (through `pyogrio`, `shapely`, and `pyproj`) ship
   binary wheels with their C libraries bundled.
4. The one thing that genuinely needs a container — unattended runs on ECS/Fargate or similar — is
   a nice-to-have.

Revisit if event-driven operation is funded, or if NSIDC ops standardizes on containers.

**Keeping the deferred work cheap.** Option B must make two choices carefully so that event-driven
work, if it comes, does not redo them:

- The storage module must be an interface, not a set of `if path.startswith("s3://")` branches.
- `Config` should be constructible from a dict, not only from a file (`config.py:87`).

The deferred work itself — a container image, stdout or structured logging, an invocation
entrypoint, an idempotent per-granule unit of work, and retry semantics — is listed in §6.3 and not
sized.

---

## 5. Cost and data movement

### 5.1 Prices

us-west-2 list prices, October 2026. Re-check before quoting.

| Charge | Price | Applies to |
|---|---|---|
| S3 data transfer out to the internet | ~$0.09/GB (first 10 TB/month) | Today's copy to `nusnow` |
| S3 ↔ EC2 data transfer, same region | $0 | All options |
| NAT gateway data processing | ~$0.045/GB, both directions | Any S3 traffic routed through NAT. An S3 gateway endpoint avoids it entirely. |
| S3 requests (GET, LIST, HEAD, PUT, COPY) | Per request | All options. Small next to the above. GETs are billed to the bucket owner unless Requester Pays is enabled. |

Requester Pays did not come up and is assumed not to be in use (N7).

### 5.2 Times each data file crosses the network

| Step | A1 | A2 | B, one identity | B, two identities |
|---|---|---|---|---|
| Bring the file to the instance | 1 (copy) | 0 | 0 | 0 |
| netCDF metadata read | local disk | byte ranges | byte ranges | byte ranges |
| Checksum | local disk | 1 (through mount) | 0 (S3 computes it during the copy)\* | 0 (combined with staging) |
| Stage to the destination | 1 (upload) | 2 (read, then upload) | 0 (server-side copy) | 2 (streamed in and out) |
| **Total** | **2** | **3** | **0**\* | **2** |
| Local disk to size | Largest batch | None | None | None |

\* Files over 5 GB need one read to compute the SHA-256 (§3.4), so 1.

### 5.3 What that means in dollars

- **Through an S3 gateway endpoint:** data transfer costs nothing for any option. The differences
  between options are time, disk, and operator effort, not dollars.
- **Through a NAT gateway:**

  | | Today (`nusnow`) | A1 | A2 | B, one identity | B, two identities |
  |---|---|---|---|---|---|
  | $ per TB of data processed | ~$90 | ~$90 | ~$135 | ~$0 | ~$90 |

  Under NAT, Option A saves no money compared with today. The remedy is an S3 gateway endpoint in
  the mediation VPC, whose endpoint policy permits the provider buckets — a network configuration
  change, not MetGenC work.
- **Not quantified:** EC2 instance hours, EBS for A1, and request charges. These are similar across
  options or small, except EBS for A1.

### 5.4 What is still needed for real numbers

- Granule volumes and processing rates per collection, to turn $/TB into $/year (N5).
- The mediation VPC's S3 routing (N2).
- The access case for each provider (N1).

---

## 6. FY27 work breakdown

Sizes are **relative** (S / M / L), not hours. They are engineering judgment against the call sites
in §3.2, not estimates derived from a prototype.

### 6.1 Option A (W1–W6)

| ID | Workstream | Size | Depends on | Notes |
|---|---|---|---|---|
| **W1** | EC2 host: Terraform from the NGAP AMI; Python environment; MetGenC install | **M** | Ops | The base for every option. |
| **W2** | Destination identity: cross-account role for the Cumulus staging bucket and Kinesis (#302); retire static keys and `metgenc-env.sh` for cloud use | **S** | Ops | `aws.py` unchanged (§3.4). |
| **W3** | Source access per provider (#301): bucket-policy grant (ask for Case 1a) or provider-account role | **S** per provider | Providers | Recurs with each provider onboarded. |
| **W4** | EDL credentials from Secrets Manager or SSM into `EARTHDATA_*` (#303) | **S** | W1 | `collection_metadata.py:69-71` unchanged. |
| **W5** | CloudWatch: agent ships `log_dir`; metric filters and alarms | **S** | W1 | No code change (§3.2, seam 6). |
| **W6a** | A1 input path: copy runbook, EBS sizing, cleanup | **S** | W1, W3 | |
| **W6b** | A2 input path: Mountpoint spike, then mount configuration and runbook | **S** | W1, W3 | The spike installs `mount-s3` on the NGAP AMI and runs one netCDF and one CSV collection end to end under both credential cases, timed against A1. If it fails, fall back to W6a. |

Option A in total: one M and five S, plus an S per provider onboarded. Do W6b first among the input
paths, since it decides between A1 and A2.

### 6.2 Option B adds (W7–W11)

Option B needs W1–W5, plus the following, and no W6.

| ID | Workstream | Size | Depends on | Notes |
|---|---|---|---|---|
| **W7** | Storage interface for input locations; port seams 1 and 3 (paginated listing, size) | **L** | — | Design as an interface, not URI-sniffing branches (§4.6). Replaces the eager `glob` at `metgen.py:500`. Can start before W1. |
| **W8** | netCDF over S3 by byte range; choose the route (§3.3); close the `Dataset` handle | **M** | W7 | |
| **W9** | S3-native staging and checksum: server-side copy with S3-computed SHA-256 (one identity); streamed hash-and-upload (two identities); the over-5 GB path | **M** | W7, N1 | Verify `copy_object` checksum behaviour against real S3 and in `moto` before relying on it. |
| **W10** | Per-location credentials: optional source profile or role name in the `.ini`; one boto3 session per location in `aws.py` | **M**, or none | N1 | Needed only if any provider is a two-identity case. |
| **W11** | Tests for the S3 input path | **M** | W7 | `moto` is already in use in `tests/test_aws.py`. The `tmp_path` churn is in `tests/test_metgen.py:107-115` and many call sites. |

Option B in total: Option A's W1–W5, plus one L and three to four M. W1–W5 carry over unchanged,
so funding Option A first and Option B later wastes nothing except W6.

**Suggested ordering for Option B:**

1. Start W7 immediately — it does not need the EC2 host — with W8 and W11 alongside it.
2. Run W1–W5 in parallel, against ops availability.
3. Do W9 and W10 once N1 is answered for the first provider.

### 6.3 Deferred (not sized)

| ID | Item | Revisit when |
|---|---|---|
| D1 | Container image and CI image build | Event-driven operation is funded, or ops standardizes on containers |
| D2 | Logging to stdout or structured JSON | Needed by D1 |
| D3 | Event-driven invocation: entrypoint, config-as-data, idempotent per-granule unit, retry semantics | Event-driven operation is funded |
| D4 | Output locations as `s3://` (seam 4) | MetGenC runs on compute with no durable local disk |

---

## 7. Open questions and risks

Living table. Record answers in §8.1, and update a status here in the same edit.

### 7.1 Open questions

| # | Question | Why it matters | What it blocks | Owner | Status |
|---|---|---|---|---|---|
| N1 | For each provider: a bucket-policy grant (to which principal?) or a role in the provider's account? | Decides whether server-side copy is available and whether W10 is needed | W3, W9, W10 | Ops, with providers | Open — plan for both |
| N2 | Does the mediation VPC reach S3 through a gateway endpoint or a NAT gateway? If an endpoint, does its policy allow provider buckets? | Decides whether any option saves dollars compared with today (§5.3) | §5 numbers | Troy / ops | Open |
| N3 | Where will operator-supplied premet/spatial files live in the cloud — instance disk, an NSIDC bucket, or the provider's bucket? | Option A needs a runbook answer; Option B handles any answer | W6, W7 detail | Lauren / Julia | Open |
| N4 | Does Mountpoint run on the NGAP AMI, and does MetGenC work and perform acceptably over it? | Decides between A1 and A2 | W6b | Project team (spike) | Open |
| N5 | What are granule volumes and processing rates per collection? | Turns $/TB into $/year | §5 | Kevin | Open |
| N6 | Do any provider buckets use SSE-KMS with provider-managed keys? | The key policy must also grant decrypt | W3 | Providers | Did not come up |
| N7 | Are any provider buckets Requester Pays? | Shifts request and transfer charges to NSIDC | §5 | Providers | Did not come up; assumed no |
| N8 | Do any granule files exceed 5 GB? | Server-side SHA-256 needs a single `copy_object`, limited to 5 GB | W9 | Kevin — answerable from our data | Open |

### 7.2 Closed questions

All closed at the 2026-09-14 meeting unless noted.

| # | Question | Answer |
|---|---|---|
| Q1 | What does Earthdatapub CUE require of MetGenC? | Providers deliver source data in their own S3 bucket, usually in another account. MetGenC must read it and stage data and metadata to the destination across different authentication and authorization. No invocation contract. |
| Q2 | What will I&A build that MetGenC would otherwise own? | Nothing that affects MetGenC. Not a scope consideration. |
| Q3 | Which invocation models must be supported? | Operator-driven: must. Event-driven: nice-to-have. |
| Q4 | Target compute? | EC2: must (NGAP AMI, Terraform). Container: optional; recommend only if clearly better by clear criteria. |
| Q5 | Who owns the source buckets, in what region, and are they Requester Pays? | Provider-owned; likely us-west-2; very likely not the destination account's owner. Requester Pays did not come up. |
| Q6 | netCDF-3 vs netCDF-4 mix? | netCDF-3 never needs to be read. |
| Q7 | Can NSIDC edit filenames once data is in the cloud? | Operators do not rename or reorganize files today, so nothing changes. Recorded as a limitation (R6). |
| Q8 | How long must on-prem and cloud run in parallel? | Indefinitely; the length of the transition is genuinely uncertain. |
| Q9 | Monitoring, alerting, and error reporting? | Logs streamable to CloudWatch so that alerts can be created. |
| Q10 | Can one granule's files span buckets or accounts? | Data files for a run always come from one bucket in one account. Where ancillary files live is open (N3). |

### 7.3 Risks

- **R1 — NAT routing erases the dollar case for Option A** (and for Option B with two identities).
  *Mitigation:* answer N2; if it is NAT, request an S3 gateway endpoint.
- **R2 — Providers default to Case 2** (role in their account), removing server-side copy.
  *Mitigation:* ask for Case 1a during onboarding. Option B still removes the copy step and the
  disk.
- **R3 — `s3fs` dependency conflict.** `aiobotocore` pins `botocore` narrowly and can conflict with
  `boto3`. *Mitigation:* the boto3 range-reader route (§3.3).
- **R4 — Test churn underestimated.** W11 touches many existing tests. If W7 lands before W11 is
  thought through, the storage interface gets shaped by test convenience rather than design.
- **R5 — Mountpoint performance on HDF5 random reads is unknown.** *Mitigation:* the W6b spike
  measures it; A1 is the fallback.
- **R6 — No renaming in a provider's bucket.** NSIDC cannot rename or reorganize files inside a
  provider's bucket. That is not done today, but if it is ever needed it must happen at staging
  time (destination key ≠ source key), which MetGenC does not support. Granule identity and
  grouping come from filenames (`metgen.py:561-579`, `granule_regex`) and must work on provider
  names as given.

Removed since the earlier draft: superseded work by I&A (Q2 closed); netCDF-3 forcing full
transfers (C6); container image weight (container deferred).

---

## 8. Decision record

### 8.1 Answers log

| Date | Who | Covered | Notes |
|---|---|---|---|
| 2026-09-14 | Troy, Kara, Lisa K, Lauren (MetGenC product owner), Julia (MetGenC co-developer), Kevin | Q1–Q10; funding | Funding may not extend beyond Option A. Describe Option A fully — tasks, benefits, and the costs of copying data — and be explicit that it is sub-optimal but works. Recommend Option B. |
| 2026-10-13 | Kevin (follow-up) | Region, identities, encryption, Requester Pays, mount, provisioning, Docker, audience | us-west-2; S3 routing from the VPC unknown. Destination S3 and Kinesis use one identity; plan for both source cases. KMS and Requester Pays did not come up. A mount is likely acceptable but untried. EC2 comes from the NGAP AMI via Terraform. On-prem does not use Docker. Event-driven is a nice-to-have. DAAC management decides from this document. No further stakeholder meetings planned. |

### 8.2 Changes from the earlier draft

- **Cost argument corrected.** Running in-region removes internet egress for every option,
  Option A included. Option A's shortfall is operational unless S3 traffic goes through NAT (§1.3,
  §5).
- **Option A specified fully**, as two variants, A1 (copy) and A2 (mount), with its own work
  breakdown (§4.2, §4.3, §6.1).
- **Option B narrowed.** The container is dropped from B and deferred (§4.6). Only the input side
  is ported; outputs and logs stay local (§3.2).
- **Option C dissolved into deferred work**, now that CUE is known to impose no invocation contract
  (§4.6).
- **Two source-access cases added** (§4.5). The claim that `aws.py` needs no change is now
  conditional (§3.4).
- **Checksum claim corrected.** `head_object` cannot be relied on for a CNM-valid SHA-256; a
  server-side copy that requests SHA-256 can (§3.4).
- **Smaller fixes.** The container's native-dependency claim is corrected (no direct GDAL
  dependency); the boto3 client count is corrected (four, not five).
- **Register and appendix.** Q1–Q10 are closed (§7.2) and new questions N1–N8 added. The per-person
  interview scripts are removed, since no further meetings are planned.
