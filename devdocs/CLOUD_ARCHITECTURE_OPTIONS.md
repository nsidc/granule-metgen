# Cloud-ifying MetGenC — Architecture Options and FY27 Scope

**Status:** Draft — reconnaissance for [issue #341](https://github.com/nsidc/granule-metgen/issues/341)
**Baseline:** MetGenC v1.16.0 (`bf5abd5`)
**Audience:** MetGenC engineers and the FY27 project planners

---

## 1. Purpose and scope

Issue #341 asks for a scope of requirements and goals for a future FY27 project to make
MetGenC work in the cloud. This document is that scope. It is reconnaissance, not
implementation: no code in this repository changes as a result of it.

**What this document does:**

- States, with specific call sites, exactly where MetGenC is coupled to a local POSIX
  filesystem and to a human-on-a-VM operating model.
- Presents three architecture options at increasing depth of commitment, and recommends one.
- Sizes the resulting work into FY27 workstreams.
- Records the open questions that block decisions, and who can answer each.

**What this document deliberately does not do:**

- It does not decide the target compute platform. That decision is not yet ours to make.
- It does not resolve the Earthdatapub CUE requirements or the I&A scope boundary. Both are
  marked **UNKNOWN** throughout. The recommendation is constructed so that it remains valid
  under any reasonable answer to either.
- It does not contain benchmark numbers. No prototype was built and no code was run.

Where this document asserts a technical fact about the current codebase, it cites
`file:line`. Where it asserts something about the future, it says so.

---

## 2. Drivers and constraints

### 2.1 Why this work exists

From the stakeholder discussion recorded in #341:

1. **Cost.** Data increasingly already lives in S3. Today MetGenC can only read from a local
   filesystem, so operating on that data means copying it out of S3 onto `nusnow` first. That
   copy costs NSIDC and data producers money, and it is pure waste — MetGenC is going to write
   the results straight back into S3 anyway.
2. **Earthdatapub CUE** will require MetGenC to run in the cloud. The specific requirements are
   **UNKNOWN**.
3. **Enterprise reach.** Suzanne's spring experiment proved one granule could be processed on
   one NSIDC EC2 instance against a local bucket. Stakeholders were explicit that this is
   "bare minimum with some heavy lifting" and does not constitute a cloud-capable MetGenC.

### 2.2 Constraints

| # | Constraint | Source | Consequence |
|---|---|---|---|
| C1 | **One codebase must keep supporting the on-prem VM workflow.** Hard requirement. | Amy Fitz's question, confirmed as a requirement | Rules out a cloud fork. Forces a storage abstraction that resolves both local paths and `s3://` URIs from the same code. |
| C2 | Invocation may be operator-driven (as today) **and/or** unattended/event-driven. CUE-invoked is a third possibility. | Stakeholders | The design must not assume a terminal, a human, or a config file on local disk. |
| C3 | Target compute is plausibly EC2 in the mediation account **or** ECS/Fargate. Not decided. | Suzanne's test used EC2 | Favors a deployment artifact that is compute-agnostic — i.e. a container. |
| C4 | Source granules may live in a **producer-owned cross-account bucket** or an **NSIDC-owned bucket**. Ownership and access model partly **UNKNOWN**. | #341, #302 | Credential design must accommodate cross-account role assumption, and the cost analysis depends on facts we do not yet have. |

### 2.3 The two standing unknowns

These are called out here, once, because they recur throughout:

- **UNKNOWN-CUE.** What Earthdatapub CUE integration requires of MetGenC — the interface, the
  invocation contract, the error and status reporting, the packaging. Nothing in this document
  should be read as having assumed an answer.
- **UNKNOWN-I&A.** Which parts of this problem I&A will solve independently, and therefore
  which parts MetGenC should not invest in. Stakeholders accepted that this reconnaissance
  proceeds anyway, on the understanding that not all of it may be usable.

Both appear in the register in §8 with the specific decisions they block.

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

### 3.2 The porting surface: five seams, ~12 call sites

This is the single most decision-relevant finding of the reconnaissance, and it is good news.
MetGenC's coupling to the local filesystem is **small and well-localized**. It is not diffused
through the codebase; it sits in five identifiable places.

| # | Seam | Call sites | Notes |
|---|---|---|---|
| 1 | **Listing** (granule discovery) | `metgen.py:500` — `[p for p in Path(configuration.data_dir).glob("*")]`<br>`metgen.py:523-537` — `ancillary_files()`, same pattern for premet/spatial dirs | `Path().glob("*")` is non-recursive and **eager**: it materializes the entire directory listing before the lazy per-granule generator (added in `599cb7b`) engages. An S3 lister must be paginated. |
| 2 | **Reading bytes** | `readers/netcdf_reader.py:36` — `Dataset(netcdf_path)`<br>`readers/utilities.py:73` — `open(premet_path)`<br>`readers/utilities.py:331` — `open(spatial_path)` | Only three reads in the whole production path. The netCDF one is the hard one — see §3.3. |
| 3 | **Stat and checksum** | `metgen.py:301-305` — `os.path.getsize()` in `Granule.size()`<br>`metgen.py:986` — `os.path.getsize(file)`<br>`metgen.py:1017-1027` — `checksum()`, streaming SHA-256 over `open(file, "rb")` | S3 already provides size via `head_object`, and can provide checksums. This seam may largely *disappear* rather than be ported. |
| 4 | **Writing outputs** | `config.py:76-80` — `ummg_path()` / `cnm_path()`, pure `Path` joins<br>`metgen.py:835` — UMM-G write<br>`metgen.py:915` — CNM write<br>`metgen.py:1179` — `output_file_path.glob("*.json")` in `validate()`<br>`metgen.py:1222` — `open(json_file)` in `apply_schema()` | Also `metgen.py:337`: `# TODO: Do any prep actions, like mkdir, etc` — output directories are never created and must pre-exist. |
| 5 | **Staging to S3** | `metgen.py:841-854` — `open(fn, "rb")` then `aws.stage_file(...)` → `aws.py:67` `upload_fileobj` | Currently a full local read followed by an upload. When the input is already in S3 this should become a server-side copy. |

Plus one seam that is not about data but blocks containerization outright:

| # | Seam | Call sites | Notes |
|---|---|---|---|
| 6 | **Logging to NFS** | `constants.py:28` — `DEFAULT_LOG_DIR = "/share/logs/metgenc"`<br>`metgen.py:78-83` — `os.path.join(log_dir, ...)` → `logging.FileHandler(log_path, "a")`<br>`config.py:448-456` — validates the dir exists **and** is writable | The file handler is **not optional**. A missing or unwritable log directory kills startup. Any container needs this to be a configurable sink. |

### 3.3 The netCDF reader is the one genuinely hard seam

`netCDF4.Dataset` (`readers/netcdf_reader.py:36`) cannot open an `s3://` path. There are three
viable strategies, and they differ materially in how many bytes cross the wire:

| | Strategy | Bytes transferred | Works for |
|---|---|---|---|
| **(a)** | Download the object to a local temp file, then `Dataset(path)` | Whole object | Everything. Simplest. |
| **(b)** | Read the object into memory, then `Dataset(name, memory=<bytes>)` | Whole object | Everything. No temp file, so no disk sizing problem in a container — but a memory sizing problem instead. |
| **(c)** | `xarray` over an `fsspec`/`h5netcdf` file object, lazy byte-range reads | Attributes + the coordinate variables actually touched | **netCDF-4 / HDF5 only.** netCDF-3 classic requires the `scipy` engine and a full read. |

Strategy (c) is attractive because of a fact easy to miss: **the reader never reads bulk science
data.** It extracts global attributes and coordinate variables to derive temporal and spatial
coverage. For a large granule that is a tiny fraction of the file. `xarray` is *already* a
declared dependency (`pyproject.toml:17`) though currently unused in production code.

Two secondary observations on this file:

- The `Dataset` handle at `netcdf_reader.py:36` is **never closed** — there is no context
  manager. Harmless in a short CLI run; a file-descriptor leak in a long-running or
  high-throughput cloud process.
- Reader dispatch is by local file suffix (`readers/registry.py:16-20`, via
  `metgen.py:472-490`). Only `.nc` maps to a real reader; everything else falls through to
  `generic.extract_metadata`, which **never opens the data file at all**
  (`readers/generic.py:7-34`). So CSV/TXT/JPEG collections require no data-file read today —
  seam 2 only bites for netCDF collections.

**This document does not choose between (a), (b), and (c).** The choice depends on the netCDF-3
vs netCDF-4 mix across the collections we actually process, and on real transfer volumes.
Deciding it is a bounded, cheap experiment early in FY27 — see workstream W2 in §7.

### 3.4 Facts that make the port cheaper than it looks

- **`aws.py` needs no credential change at all.** All five boto3 call sites
  (`aws.py:17`, `:29`, `:44`, `:56`) use a bare `boto3.client(...)` on the **default credential
  chain**. An EC2 instance role or ECS task role therefore works today with zero code edits.
  What must change is the *operator workflow*: `scripts/metgenc-env.sh` exports static access
  keys scraped from a named profile. **That, and not `aws.py`, is what issue #302 is really
  about.**
- **EDL auth is one line.** `collection_metadata.py:69-71` hardcodes
  `earthaccess.login(strategy="environment", ...)`. A Secrets Manager path (#303) is satisfied
  either by injecting the same environment variables at task start — no code change — or by
  changing that single call. Cheap either way. Note the hardcoded strategy also means `.netrc`
  and interactive login are unreachable today, despite what the earthaccess error message
  advertises.
- **Staging can become a server-side copy.** When input is already in S3, seam 5 becomes
  `copy_object` — the bytes never leave AWS. Similarly `head_object` supplies size and can
  supply checksums, potentially collapsing seam 3 entirely.
- **There is prior art to build on, not duplicate.** `devdocs/PIPELINE_REFACTORING_PLAN.md:270`
  already sketches the pipeline steps `CreateUMMG, CreateCNM, WriteFile, S3Upload, SendMessage`,
  and `tests/integration/configs/IRWIS2DUCk.ini:10-12` carries a commented-out `[Pipeline]`
  section. Option C in §4 is a continuation of that thinking, not a new direction.

### 3.5 Configuration is local-file-only

`config.py:87` requires the `.ini` to be an existing local file, and `validate()`
(`config.py:376-396`) requires `os.path.exists()` on `data_dir`, `premet_dir`, `spatial_dir`,
and `local_output_dir`. There are **no auth keys of any kind in the `.ini`** — no EDL
credentials, no AWS profile, no region, no role ARN. All authentication is ambient environment.
That is a good property to preserve.

Two incidental defects noticed during the survey, worth fixing whenever those files are next
touched but not part of this scope: `checksum_type` is parsed into `Config` but never read
(SHA-256 is hardcoded at `metgen.py:1017-1027` and in `templates/cnm_files_template.txt:5`),
and `date_modified` in `tests/integration/configs/IPFLT1B_DUCk.ini:13` is not a recognized key
and is silently ignored.

---

## 4. Options

The three options are **nested**: A ⊂ B ⊂ C. They are not competing bets. They are depths of
commitment, and the honest way to read them is "how far up this ladder does FY27 go?"

### Option A — Lift and shift

**What changes.** Nothing in the application. Run today's CLI, unmodified, on an EC2 instance in
the mediation account. Inputs reach it by `aws s3 sync` or a mounted filesystem. Resolve
issues #301 (bucket access), #302 (cross-account assumable role in place of profile keys), and
#303 (EDL secrets).

**What it buys.** It is cheap and it preserves the operator workflow exactly. It is also
already partly proven — this is what Suzanne demonstrated.

**What it costs.** A persistent instance, and the operational overhead of maintaining it.

**What it leaves unsolved.** *The cost driver, which is the primary justification for the whole
effort.* Data is still copied out of S3 — to a different machine, but copied. It also cannot
serve event-driven or CUE invocation, and it does not generalize past one NSIDC instance.

**Assessment.** Option A is best understood as **a precise statement of what the three existing
tickets actually deliver**. It is useful in this document for exactly that framing purpose. It
is not a recommendation, and stakeholders were already right to say the three tickets are not
enough.

### Option B — Storage abstraction + container **(recommended)**

**What changes.**

1. A single storage-resolution module. Each of `data_dir`, `premet_dir`, `spatial_dir`,
   `local_output_dir`, and `log_dir` accepts either a local path or an `s3://` URI, and all
   six seams from §3.2 route through it.
2. A Dockerfile, so one artifact runs on EC2 or Fargate without the choice being made now.
3. S3-native optimizations where input is already in S3: `copy_object` for staging (seam 5) and
   `head_object` for size and checksum (seam 3).
4. The logging sink becomes configurable rather than a mandatory NFS `FileHandler` (seam 6).

**What does *not* change:** the CLI, the `.ini` configuration format, and the operator workflow.
An operator on the VM keeps typing exactly what they type today, with local paths, and it keeps
working. **This is what satisfies constraint C1**, and it is why the abstraction is the right
shape rather than merely a convenient one — the same seam that enables the cloud is the seam
that preserves on-prem.

**What it buys.** It is the option that actually attacks the egress cost, because in-region
S3 → compute transfer is free and server-side copy moves no bytes at all. It keeps one codebase.
It is compute-agnostic, so it does not require resolving C3 before starting. And it is achievable
against ~12 call sites.

**What it costs.** Real but bounded engineering across those seams, plus test churn — the unit
tests construct real temp directories and pass `Path` objects directly into the grouping
functions (`tests/test_metgen.py:107-115` and many call sites), so the storage seam ripples
through them.

**Open question inside it.** The netCDF read strategy, §3.3. This does not block starting; it
blocks finishing seam 2.

**Which unknowns could invalidate it.** UNKNOWN-I&A could, if I&A independently builds a
cloud-native metadata generator that supersedes MetGenC. UNKNOWN-CUE cannot — every one of
these changes is a prerequisite for any cloud operation, whatever CUE turns out to require.

### Option C — Pipeline / invocable service

**What changes.** Option B, plus decoupling the core from the CLI:

- A callable, idempotent per-granule unit of work that something other than a human can invoke.
- Configuration accepted as **data**, not as a file on local disk (`config.py:87` today).
- Structured logging to CloudWatch rather than a file handler.
- Retry and error-reporting semantics appropriate to unattended operation.

**What it buys.** This is what CUE-invoked or Cumulus-invoked operation would require, and what
event-driven per-granule processing would require. It builds directly on
`devdocs/PIPELINE_REFACTORING_PLAN.md`.

**Assessment.** **Option C is not scopeable until UNKNOWN-CUE is resolved.** Attempting to
specify the invocation contract now would be inventing a requirement. Its value in this document
is different: it tells us which seams Option B must choose carefully so that C, when it comes,
does not require redoing them. Specifically — the storage module should be an interface rather
than a set of `if path.startswith("s3://")` branches, and configuration should be
constructible from a dict rather than only from a file.

---

## 5. Recommendation

**Target Option B for FY27, sequenced so that Option C remains reachable without rework.**

The reasoning:

- Option A does not solve the problem the project exists to solve. Saying so plainly is the most
  useful thing this reconnaissance can contribute, because it corrects the impression that
  #301/#302/#303 constitute the cloud work.
- Option B is the smallest change that actually addresses the cost driver, and constraint C1
  (one codebase, both environments) makes the storage abstraction mandatory rather than
  optional. We get the cloud capability and the on-prem preservation from the same piece of work.
- Option C cannot responsibly be scoped yet, and pretending otherwise would produce a plan that
  the first CUE conversation invalidates.

**Explicit robustness claim, stated so it can be checked:** every workstream in §7 is a
prerequisite for cloud operation under *any* answer to UNKNOWN-CUE and any choice of compute
under C3. If a future conversation reveals that one of them is not, that is a defect in this
document and it should be revised.

The one place where the recommendation is genuinely contingent is UNKNOWN-I&A. If I&A intends to
own cloud metadata generation, the correct FY27 scope may be much smaller than Option B. This is
the highest-value question to resolve first, and it is why it sits at the top of the register.

---

## 6. Cost and egress analysis

This is the argument and its variables, not a spreadsheet. The numbers require facts we do not
have yet — see the UNKNOWNs at the end of this section.

### 6.1 The structure of the argument

- **Today:** granules are copied from S3 to `nusnow` over the public internet. S3 egress to the
  internet is billed per GB. Every processed byte is paid for.
- **In-region compute:** S3 → EC2/Fargate **in the same region as the bucket** incurs no data
  transfer charge. This is the entire cost case for Option B, and it holds regardless of which
  compute we pick.
- **Cross-region compute** reintroduces a per-GB inter-region charge — smaller than internet
  egress, but not zero. Source bucket regions therefore matter.
- **Requester Pays buckets** shift the charge to us rather than the producer. Whether producer
  buckets are configured this way is unknown and changes who benefits from the fix.

### 6.2 Where the bytes go, per strategy

| Path | Bytes moved today | Bytes moved under Option B |
|---|---|---|
| Read granule for metadata (seam 2) | Whole object, S3 → internet | Whole object in-region under (a)/(b); **attributes + coordinate variables only** under (c) |
| Compute size + checksum (seam 3) | Whole object read from local disk | Zero, if `head_object` supplies both |
| Stage to Cumulus bucket (seam 5) | Whole object read from disk, then uploaded | Zero, via server-side `copy_object` |

The seam-5 saving is the one that is unconditional and large: today every staged byte is read
out of storage and written back over the wire. A server-side copy moves none of it through our
compute at all.

### 6.3 UNKNOWNs blocking the numbers

- Granule volumes and processing rates per collection.
- Which regions the source buckets are in.
- Whether producer buckets are Requester Pays.
- The netCDF-3 vs netCDF-4 mix, which decides whether strategy (c) is available.

*Kevin to obtain.* Until then, the cost case rests on the structural argument above, which is
sound but unquantified.

---

## 7. FY27 work breakdown

Sizes are **relative** (S / M / L), not hours. They are engineering judgment against the call
sites in §3.2, not estimates derived from a prototype.

| ID | Workstream | Size | Depends on | Notes |
|---|---|---|---|---|
| **W1** | Storage abstraction module; port seams 1, 3, 4 (listing, stat/checksum, output writing) | **L** | — | The core of Option B. Design as an interface, not URI-sniffing branches, so Option C does not require redoing it. Paginated S3 listing replaces the eager `glob` at `metgen.py:500`. |
| **W2** | netCDF read strategy: bounded experiment on (a)/(b)/(c), then port seam 2 | **M** | Collection netCDF-3/4 mix | The experiment is small and should come early — it is the only genuine technical unknown inside Option B. `xarray` is already a dependency. |
| **W3** | S3-native staging: `copy_object` for seam 5, `head_object` for seam 3 | **S** | W1 | Highest cost saving per unit of effort. Note SHA-256 is hardcoded at `metgen.py:1017-1027`; reconcile with S3-provided checksums. |
| **W4** | Credentials and secrets: cross-account assumable role (#302), Secrets Manager or task-injected EDL (#303), retire `metgenc-env.sh` for cloud use | **M** | C4 answered | `aws.py` itself needs no change (§3.4). The work is the operator workflow, the role/trust policy, and one line at `collection_metadata.py:69-71`. Largely an ops collaboration. |
| **W5** | Configurable logging sink to replace the mandatory NFS `FileHandler` (seam 6) | **S** | — | Blocking for containerization; independent of everything else; could go first. |
| **W6** | Containerization: Dockerfile plus a CI image build | **M** | W5 | Nothing exists today. netCDF/GDAL/geopandas native dependencies make the image non-trivial. Satisfies C3 without deciding it. |
| **W7** | Test strategy for the storage seam | **M** | W1 | Unit tests construct real `tmp_path` directories and pass `Path` objects directly (`tests/test_metgen.py:107-115`); the seam ripples through them. `moto` is already in use in `tests/test_aws.py` and extends naturally to S3 input. |
| **W8** | Bucket and IAM provisioning (#301) | **S** | C4 answered | Likely an ops dependency rather than code. |
| **W9** | *(Option C, unscopeable)* Invocable interface, config-as-data, structured logging, retry semantics | **?** | **UNKNOWN-CUE** | Do not estimate until CUE requirements exist. W1's interface design is what keeps this cheap later. |

**Suggested ordering:** W5 and W2's experiment first (both small, both unblock decisions), then
W1, then W3 and W7 alongside it, with W4/W6/W8 sequenced against ops availability.

---

## 8. Risks and open questions register

Living table. Update as answers arrive; the log in §9.5 is where the answers themselves go.

| # | Question | Why it matters | What it blocks | Owner | Status |
|---|---|---|---|---|---|
| Q1 | **What does Earthdatapub CUE require of MetGenC?** Interface, invocation contract, packaging, status reporting. | CUE is a stated driver of the whole effort. | All of Option C (W9). Does **not** block W1–W8. | Kevin, via Kara/Lisa K | **UNKNOWN** |
| Q2 | **What will I&A build that MetGenC would otherwise own?** | Determines whether FY27 effort is superseded. | The scope of the recommendation itself — potentially all of it. | Kevin, via stakeholders | **UNKNOWN** |
| Q3 | Which invocation model(s) must be supported — operator, event-driven, CUE-invoked? | Decides whether config-as-data and structured logging are FY27 or later. | W9 scope; influences W5. | Kara / Lisa K | Open |
| Q4 | Target compute: EC2 in the mediation account, ECS/Fargate, or other? | Decides the deployment artifact and IaC. | W6 detail. Option B is deliberately compute-agnostic, so it does not block starting. | Troy / ops | Open |
| Q5 | Who owns the source buckets? What region? Requester Pays? | Determines cross-account role design and who actually saves money. | W4, W8, and all of §6's numbers. | Kevin, via producers | Open |
| Q6 | What is the netCDF-3 vs netCDF-4 mix across our collections? | Decides whether lazy byte-range reads (strategy c) are available. | W2. | Kevin — answerable from our own data | Open |
| Q7 | **Can NSIDC edit filenames once data is in the cloud, or must the PI?** | MetGenC derives granule identity and grouping from filenames (`metgen.py:561-579`, `granule_regex`). If we lose the ability to rename, that logic must cope with producer-chosen names as given. | Reader/grouping scope; possibly new config surface. | Amy Fitz / producers | Open |
| Q8 | How long must on-prem and cloud run in parallel, and is on-prem ever retired? | C1 is treated as permanent; if it is temporary, some complexity could be deferred. | Long-term shape of W1. | Stakeholders | Open |
| Q9 | What monitoring, alerting, and error reporting is expected in the cloud? | Today errors go to a terminal and an NFS log file. Unattended operation needs somewhere else. | W5 detail, W9. | Kara / ops | Open |
| Q10 | Do we need to process a granule whose files span more than one bucket or account? | Would complicate the storage abstraction significantly. | W1 design. | Kevin, via producers | Open |

**Risks not phrased as questions:**

- **R1 — Superseded work.** Q2 unresolved means FY27 effort could be duplicated by I&A.
  *Mitigation:* resolve Q2 first; W1's seams are useful to any successor design regardless.
- **R2 — netCDF strategy forces a full transfer.** If our collections are mostly netCDF-3
  classic, strategy (c) is unavailable and the per-granule read saving disappears. The seam-5
  and seam-3 savings survive.
- **R3 — Container image weight.** netCDF, GDAL, `geopandas`, `alphashape`, and `concave-hull`
  are heavy native dependencies. W6 may be larger than it looks.
- **R4 — Test churn underestimated.** W7 touches a lot of existing tests. If W1 lands before W7
  is thought through, the storage seam gets shaped by test convenience rather than design.

---

## 9. Appendix: stakeholder interview questions

Each question is tagged with the register entry it closes. Take these into the meetings; record
answers in §9.5.

### 9.1 Troy — the 1–2 hour debrief named in #341

*The single highest-value conversation. Goal: convert the three existing tickets from summaries
into specifications, and find out what he knows that isn't written down.*

1. Walk me through the EC2 test end to end. What did you actually run, on what data? **[Q4]**
2. What broke *first*? What was the sequence of failures? **[general]**
3. #302 says "use the cross account assumable role instead of cumulus profile stuff." Concretely:
   which account assumes which role, what's the trust policy, and who provisions it? **[Q5, W4]**
4. Related — I found that `aws.py` already uses the default boto3 credential chain, so an
   instance or task role should work with no code change. Does that match your understanding, or
   is there something in the mediation account that defeats it? **[W4]**
5. #303 says "maybe" on Secrets Manager, and notes it might be OBE because of #291. Is it?
   Would injecting `EARTHDATA_*` env vars at task start be acceptable, or is Secrets Manager a
   requirement rather than a preference? **[W4]**
6. What do you think the three tickets *miss*? Stakeholders said they're "bare minimum" — what's
   your version of the gap? **[Q1, Q2]**
7. What does "works across the enterprise vs. for one NSIDC EC2 instance" mean to you
   specifically? What would you need to see to call it enterprise-ready? **[Q3, Q4]**
8. EC2 or Fargate — is there an NSIDC-standard answer, or is this open? Does the mediation
   account support running containers? **[Q4]**
9. Is there an existing NSIDC container base image or deployment pattern I should conform to
   rather than inventing? **[W6]**
10. Where should cloud logs go, and what does ops expect to be alerted on? **[Q9]**
11. Who else should I be talking to that isn't on my list? **[general]**

### 9.2 Suzanne — the spring experiment

*Goal: recover the undocumented detail. The tickets are her conclusions; I want her observations.*

1. What exactly did you run — which collection, which granule, what config? **[general]**
2. What did you have to hand-hack to make it work that never became a ticket? **[general]**
3. "Some required config files aren't there when we do the install" (#302) — which files? **[W4]**
4. Did you get data from S3 directly, or copy it to the instance first? If you copied it, was
   that a deliberate choice or a workaround? **[Q5, W2]**
5. Did you hit anything in the netCDF reading path, or was your test granule small enough that
   it didn't come up? **[Q6, W2]**
6. What did you do about the log directory? `/share/logs/metgenc` won't exist on an EC2
   instance, and MetGenC refuses to start without a writable log dir. **[W5]**
7. Knowing what you know now, what would you do differently? **[general]**
8. Was there anything you concluded was fine that you're actually unsure about? **[general]**

### 9.3 Kara / Lisa K — ops and enterprise/CUE

*Goal: the invocation model and the operational contract. This conversation is the one most
likely to move Q1 and Q3.*

1. In the target state, who or what runs MetGenC — an operator, a schedule, an S3 event, or
   another system? **[Q3]**
2. What is Earthdatapub CUE expected to require of MetGenC? Does CUE call MetGenC, or does
   MetGenC feed CUE? **[Q1]**
3. Is there a defined interface or contract for CUE integration yet, or is it still being
   designed? If the latter, when will it firm up, and can MetGenC influence it? **[Q1]**
4. If MetGenC is invoked by another system, does it stay a CLI, or does it need to be a library,
   a container entrypoint, or a service? **[Q1, W9]**
5. What is I&A planning to build in this space, and where should MetGenC stop? **[Q2]**
6. Must MetGenC keep supporting operator-driven runs after CUE integration, or does CUE replace
   that workflow? **[Q3, Q8]**
7. What monitoring, alerting, and error reporting do you expect from an unattended cloud job?
   Where do failures surface? **[Q9]**
8. Does a single MetGenC run process one granule or a whole collection in the target state? This
   determines whether the per-granule unit of work needs to be independently retryable. **[Q3, W9]**
9. Are there compliance or audit constraints on where credentials live and how they rotate? **[W4]**
10. Is there an expectation that MetGenC runs in a specific AWS account or region? **[Q4, Q5]**

### 9.4 Amy Fitz / data producers

*Goal: the constraints that come from outside the project.*

1. Amy's question, back at her: is maintaining an on-prem version a hard requirement, and for
   how long? Is there a retirement date, or is dual support permanent? **[Q8]**
2. Can NSIDC rename files once they're in the cloud, or must the PI produce final names?
   MetGenC derives granule grouping and identity from filenames today. **[Q7]**
3. If we can't rename, are producer filenames stable and consistent enough for regex-based
   grouping, or does that assumption break? **[Q7]**
4. Where do producer granules live — producer-owned S3, NSIDC-owned S3, or still on local
   disk? **[Q5]**
5. For producer-owned buckets: which account, which region, and are they Requester Pays? **[Q5]**
6. Who grants us read access, and what's the approval path? **[Q5, W8]**
7. Can the files of a single granule span more than one bucket or account? **[Q10]**
8. Roughly what volumes and rates are we talking about per collection? **[§6.3]**
9. Are the science files netCDF-3 classic or netCDF-4/HDF5? This decides whether we can read
   metadata without transferring the whole file. **[Q6]**
10. Do producers expect to keep delivering premet/spatial ancillary files, and would those live
    alongside the data in S3? **[W1]**

### 9.5 Answers log

Record answers here as they come in, dated, so they sit next to the questions that prompted
them. When an answer closes a register entry in §8, update that entry's status in the same edit.

| Date | Person | Question(s) | Answer | Register entries updated |
|---|---|---|---|---|
| | | | | |
