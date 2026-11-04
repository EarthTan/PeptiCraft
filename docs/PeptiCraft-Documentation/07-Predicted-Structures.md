# 07 · Predicted structures: production, storage, presentation

## What these structures are

The three-dimensional structures on the platform are **predicted monomers of the fusion**: the
scaffold, the linker and the functional peptide concatenated in assembly order, folded once by
OmegaFold, which returns coordinates and a per-residue confidence (pLDDT).

One chain stands for one combination — one candidate peptide × one scaffold × one linker. There
are 290 candidates (254 of them distinct in sequence), seven reachable scaffolds and fifteen
linkers: 30,450 combinations, 26,670 distinct sequences after deduplication.

The limits of the prediction have to be stated plainly. Four of the reachable scaffolds are
collagen (jinbo-hc8-hc16, jinbo-col3a1-16x, wuhan-trhciii-1, trautec-col17), whose real fold is a
three-chain triple helix; the rest are silk proteins, whose fibre is a chain-to-chain beta stack.
OmegaFold is a single-sequence, single-chain predictor with no multiple-sequence alignment, and
it cannot produce any of that. What these models can show is the local geometry of the peptide
and the linker, not the assembled form of the scaffold.

All 496 constructs still point at a placeholder backbone record (`backbone_proteins.id=1`,
`4RepCT`, placeholder sequence). The fused sequence is a reconstruction from the reader's own
choices rather than a pipeline product, and rendering a reconstructed combination is the most
persuasive and least supported thing the platform can show. The page therefore carries both
figures — whole-chain and peptide-only pLDDT — and says that this is a monomer.

## How they are produced

Prediction runs on the workstation `dku-1387-tailscale`, on an RTX 5880 Ada (47 GB). The image
`igem-silk/omegafold:latest` packages the predictor as an HTTP service (port 8204,
`POST /predict`, no batch endpoint); the weights are mounted from
`/home/lenovo/Projects/iGEM-silk/tools/models` and are not re-downloaded with the container.

The service needs `OMEGAFOLD_SUBBATCH=256` set explicitly. The default is empty, which expands
the pairwise tensor to the full sequence length: a 1,106-residue chain asks for 40.32 GiB while
the service itself already holds about 15 GiB of the card's 47 GiB, and fails with
`CUDA out of memory`. A value of 1024 still asks for 34.56 GiB and fails the same way; 256
passes with a peak of 11.4 GB. In tier1, 254 of the 1,778 chains exceed 1,000 residues, so
without this parameter a quarter of the set is lost. The cost of the setting on mid-length
chains is about 12 per cent (515 residues: 135.6 s → 151.8 s).

Measured wall-clock on one device, serialised, with subbatch 256:

| Residues | 69 | 251 | 515 | 962 | 1,106 |
|---|---|---|---|---|---|
| Seconds | 1.8 | 21.1 | 152 | 741 | 1,170 |

The exponent is close to 2.35 — neither linear nor quadratic. The totals that follow from it:

| Release | Structures | Residues | Device time | PDB volume | Gzipped |
|---|---|---|---|---|---|
| tier1 — recommended linker | 1,778 | 1.00 M | 166 h (6.9 d) | 0.65 GB | 0.14 GB |
| tier1 + 2 — two linkers | 3,556 | 2.00 M | 335 h (13.9 d) | 1.30 GB | 0.29 GB |
| tier1 + 2 + 3 — exhaustive | 26,670 | 15.13 M | 2,552 h (106 d) | 9.81 GB | 2.20 GB |

The cost sits in two long scaffolds. In tier1 the 254 chains built on `juzi-fhlc` (1,071 aa) take
48 per cent (79.7 h) and the 254 on `bolt-18b` (945 aa) take 32 per cent (53.4 h); the other five
scaffolds together take 33 hours. A first pass over the five short scaffolds — 254 peptides each,
1,270 structures — therefore lands in about 33 hours, and the two long scaffolds can be added
later without repeating any of it.

The long run is held up by two Docker-supervised containers: `omegafold-batch` (the service,
`--restart unless-stopped`) and `omegafold-runner` (`fold_batch.py` over `--network host`, using
only urllib and no GPU). The batch advances in ascending sequence length, so short chains
finish first; a coordinate file that already exists is skipped, which makes a power cut, a
stopped container and a reboot cost nothing but the minutes in flight.

## Where they live, and why not on the site

The coordinate files do not go into Cloudflare Pages. That deployment has a ceiling of 20,000
files and already uses 2,128; tier1 alone is 1,778 structures and the exhaustive set is 26,670,
so the file count alone would break the limit.

An R2 bucket holds the coordinates, laid out as:

```
structures/<structure_id>.pdb     one file per prediction, named by its content-addressed id
structures.json                   per-structure metadata: chain length and the two confidences
structure_lookup.json             construct_id|scaffold|linker -> structure_id
```

The bucket is `pepticraft-structures`, read through its public development domain
`pub-e92779d3b73e46229f1118ce915547d4.r2.dev`. A browser reads all three across origins, so the
bucket carries a CORS policy allowing GET from the site's origin and from the local development
port.

Storage cost is not the constraint: 0.65 GB is inside the free allowance, and the exhaustive set
at 9.81 GB is a matter of a few cents a month. The constraint is GPU time — and 106 days of
device time is a scheduling question, not a budget one.

Publishing runs through `service/scripts/publish_structures.py`: it rebuilds the index with
`service/scripts/build_structure_index.py` (the index is rebuilt from whatever is on disk every
time, so a batch that is still running publishes the subset that has finished) and uploads what
the bucket does not yet hold. It reaches the bucket through the HTTP API with the OAuth token
wrangler already holds, rather than through rclone, so no separate R2 API token is needed. The
upload is incremental: a file already stored at the same size is not sent again. The index is
uploaded last, so an interrupted run leaves the bucket describing a set of structures that are
all present rather than pointing at coordinates that have not arrived.

`~/pepticraft-sync/sync_structures.py` is the loop around it: it copies the finished coordinate
files across from the workstation, rebuilds the index and uploads, and repeats. A launch agent
(`com.pepticraft.structure-sync`) runs it every thirty minutes, so a structure appears on the
site as soon as it exists rather than at the end of the run. The script and the manifest sit in
`~/pepticraft-sync` rather than in the repository, because a launch agent runs outside the
desktop session's privacy grants and cannot reach `~/Documents`; the agent's plist also sets the
proxy explicitly, since the session's environment variables are not inherited.

## How they are presented

The rendering is 3Dmol.js, carried with the site (`app/public/vendor/3Dmol-min.js`) rather than
fetched from a CDN at runtime. The colour is pLDDT on AlphaFold's scale: deep blue for very
confident residues, light blue for confident, yellow for uncertain, orange for disordered. The
page shows the whole-chain figure and the figure restricted to the peptide's own residues, plus a
switch that highlights the peptide — the peptide occupies the C-terminal end of the fusion, so
its position follows from the chain length.

There are two entrances: a "3D" button on every candidate row of the Builder's results, and the
construct page, where the structure appears when the URL names a scaffold and a linker, which is
the state in which the page is previewing an assembly. Both look the structure up by the same
triple, `construct_id|scaffold|linker`. A combination that has not been predicted is reported as
such rather than shown as an empty frame. The bucket is named at build time by
`VITE_STRUCTURE_BASE_URL`, which is set in `app/.env.production`; with that variable unset the
whole feature renders nothing and the platform behaves as it did before it existed. The address
is public by design, like the site's own data directory, which is why it is committed rather than
held in the dashboard settings.

## Limits and open questions

Confidence is not monotone in chain length. In the measurements a 962-residue chain reaches only
0.21 whole-chain pLDDT while a 1,106-residue chain reaches 0.58, because the stable core of the
longer chain pulls the average back up. A higher number is therefore not the same as a longer
chain being more trustworthy, and the two are read separately.

Tier1 covers the default linker only. A reader who chooses a different linker in the Builder
finds no structure for that combination until tier2 or tier3 has run.

The viewer currently draws a single-chain cartoon representation, with no ligands, no surface and
no secondary-structure annotation. The peptide highlight is a residue-range colour, not a
division by secondary-structure element.
