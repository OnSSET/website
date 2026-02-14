# Data

If you're new, you can kickstart your journey using starter datasets from the **Global Electrification Platform (GEP)**. For more experienced users, feel free to utilize your own data for deeper analysis.

## GEP Starter Datasets (58 Countries)
GEP offers [harmonized datasets](https://energydata.info/group/gep) ideal for:

- Exploring OnSSET-style inputs and outputs
- Benchmarking and sensitivity checks
- Rapid prototyping before building a full country dataset

Here’s a practical workflow for new users:

1. **Pick a country dataset** from the GEP group.
2. **Inspect available data/layers/attributes** to understand the types of data and requirements.
3. **Run a minimal scenario** using the started datasets with defaults/baseline parameters.
4. **Review & Iterate**: Adjust parameters (e.g., demand tiers, grid costs, technology assumptions, and targets) and explore sensitivities.

> **Tip:** Treat GEP as “starter inputs + reference results.” For official planning, refine and validate local inputs.

## Bring Your Own Data
When preparing a new country analysis, consider collecting both GIS and non-GIS data:

- The list of GIS data is available [here](https://onsset.readthedocs.io/en/latest/data_acquisition.html)
- The list of non-GIS data is available [here](https://onsset.readthedocs.io/en/latest/otherinputs.html)

**Note!** Before running an custom OnSSET analysis, you will need to prepare the input file so that it contains the data needed for each version of the model and those be in the appropriate format. There is a separate code for doing that which is available on the repo ["OnSSET_GIS_Extraction_notebook."](https://github.com/OnSSET/OnSSET_GIS_Extraction_notebook)

