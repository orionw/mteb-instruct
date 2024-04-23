import pandas as pd
import json
import os
import glob
import argparse
import tqdm


GRADIENT_STR = """\midpointgradientcell{VALUE}{MIN}{MAX}{MIDPOINT}{neg}{pos}{\opacity}{0}"""


model_order = {
    # non instruction tuned
    "BM25": "bm25",
    "E5-base-v2": "intfloat/e5-base-v2",
    "E5-large-v2": "intfloat/e5-large-v2",
    "Contriever": "facebook/contriever-msmarco",
    "MonoBERT": "castorini/monobert-large-msmarco",
    "MonoT5-base": "castorini/monot5-base-msmarco-10k",
    "MonoT5-3B": "castorini/monot5-3b-msmarco-10k",
    "Cohere v3 English": "cohere",
    "OpenAI v3 Large": "openai",
    "Google Gecko": "google-gecko-v2",
    # now these are instruction-tuned in some sense
    "BGE-base": "BAAI/bge-base-en",
    "BGE-large": "BAAI/bge-large-en",
    "TART-Contriever": "tart-dual-contriever-msmarco",
    "INSTRUCTOR-base": "hkunlp/instructor-base",
    "INSTRUCTOR-xl": "hkunlp/instructor-xl",
    "TART-FLAN-T5-xl": "facebook/tart-full-flan-t5-xl",
    "E5-mistral": "intfloat--e5-mistral-7b-instruct",
    "GritLM-7B": "GritLM/GritLM-7B",
    "FLAN-T5-base": "google/flan-t5-base",
    "FLAN-T5-large": "google/flan-t5-large",
    "Llama-2-7B": "meta-llama/Llama-2-7b-hf",
    "Llama-2-7B-chat": "meta-llama/Llama-2-7b-chat-hf",
    "GritLM-Reranker": "GritLM",
    "Mistral-7B-instruct": "mistralai/Mistral-7B-Instruct-v0.2",
    "FollowIR-7B": "jhu-clsp/FollowIR-7B",

}

MAP_MODEL_ORDER = {v.replace("/", "__"): k for k, v in model_order.items()}



def gather_results(args, dataset_in_table=["Robust04InstructionRetrieval", "News21InstructionRetrieval", "Core17InstructionRetrieval"]):
    # go through all in `results` and aggregate them together
    # we care only about the pairwise and rankwise scores, as well as map@1000 and ndcg@5 scores of the original and changed

    all_data = []
    for file in tqdm.tqdm(glob.glob(os.path.join(args.results_dir, "*", "*.json"))):
        dataset_name = file.split("/")[-1].replace(".json", "")
        model_name = file.split("/")[-2]
        with open(file, "r") as f:
            data = json.load(f)["test"] # all on test set

            rankwise = data["rankwise_score"]
            pointwise = data["pointwise_score"]

            # map@1000 and ndcg@5
            map1000 = data["individual"]["original"]["map_at_1000"]
            ndcg5 = data["individual"]["original"]["ndcg_at_5"]

            # map@1000 and ndcg@5 of the changed
            map1000_changed = data["individual"]["changed"]["map_at_1000"]
            ndcg5_changed = data["individual"]["changed"]["ndcg_at_5"]

            # map@100 and ndcg@5 of the base
            map1000_base = data["individual"]["base"]["map_at_1000"]
            ndcg5_base = data["individual"]["base"]["ndcg_at_5"]
            diff_map1000 = map1000 - map1000_base
            diff_ndcg5 = ndcg5 - ndcg5_base

            # add to the list
            all_data.append({
                "dataset": dataset_name,
                "model": model_name,
                "rankwise": rankwise,
                "pointwise": pointwise,
                "map": map1000,
                "ndcg@5": ndcg5,
                "map_changed": map1000_changed,
                "ndcg@5_changed": ndcg5_changed,
                "main_score": map1000 if "news" not in dataset_name.lower() else ndcg5,
                "diff_score": diff_map1000 if "news" not in dataset_name.lower() else diff_ndcg5

            })

    # create a dataframe
    df = pd.DataFrame(all_data)
    # sort by map and then rankwise
    df = df.sort_values(by=["map", "rankwise"], ascending=[False, False])
    df.to_csv(os.path.join(args.results_dir, "all_results.csv"), index=False)

    # lets turn this into a latex figure
    # aggregate by dataset, and grab only the map (for Robust and Core) or (nDCG) of the original, plus the pointwise and rankwise scores
    df = df[df["dataset"].isin(dataset_in_table)]
    df = df.groupby(["dataset", "model"]).agg({"main_score": "first", "rankwise": "first"}).reset_index()
    # for every metric, multiply by 100 and round and format to nearest tenth
    for col in ["main_score", "rankwise"]:
        df[col] = (df[col] * 100).round(1).astype(str)

    # order by model
    # breakpoint()
    df["model"] = df["model"].map(MAP_MODEL_ORDER)
    # keep only the ones that are not nan, e.g. not in the model
    # breakpoint()
    df = df[df.model.notna()]
    df["model"] = pd.Categorical(df["model"], model_order.keys())
    df = df.sort_values(by=["model"])
    # First, pivot your DataFrame to get 'model' as index and have a multi-level column with 'dataset' and the scores
    pivoted_df = df.pivot(index='model', columns='dataset')
    # Flatten the MultiIndex in columns, concatenating level values
    pivoted_df.columns = [' '.join(col).strip() for col in pivoted_df.columns.values]
    # Since you seem to wish for a specific order and naming of columns, you can explicitly reindex/organize
    # This step might need to be adjusted based on exact desired format, especially if you have dynamic datasets
    # The list of new column names should be formed based on the datasets and scores present in your original dataframe
    new_column_order = [
        'main_score Robust04InstructionRetrieval', 'rankwise Robust04InstructionRetrieval',
        'main_score News21InstructionRetrieval',  'rankwise News21InstructionRetrieval',
        'main_score Core17InstructionRetrieval', 'rankwise Core17InstructionRetrieval'
    ]
    pivoted_and_ordered_df = pivoted_df.reindex(columns=new_column_order).reset_index()
    # now add an average column at the end for both
    pivoted_and_ordered_df["main_score_avg"] = pivoted_and_ordered_df[['main_score Robust04InstructionRetrieval', 'main_score News21InstructionRetrieval', 'main_score Core17InstructionRetrieval']].astype(float).mean(axis=1).apply(lambda x: str(round(x, 1)))
    pivoted_and_ordered_df["rankwise_avg"] = pivoted_and_ordered_df[['rankwise Robust04InstructionRetrieval', 'rankwise News21InstructionRetrieval', 'rankwise Core17InstructionRetrieval']].astype(float).mean(axis=1).apply(lambda x: str(round(x, 1)))

    min_values = {}
    max_values = {}
    midpoint = {}
    for col in pivoted_and_ordered_df.columns:
        if "model" not in col:
            min_values[col] = pivoted_and_ordered_df[col].astype(float).min()
            max_values[col] = pivoted_and_ordered_df[col].astype(float).max()
            midpoint[col] = pivoted_and_ordered_df[col].astype(float).mean()

    # replace all values that aren't the model names with ``
    for i, col in enumerate(pivoted_and_ordered_df.columns):
        if "model" not in col:
            if "rankwise" in col:
                x_format = lambda x: str(x) if "-" in str(x) else "+"+str(x)
            else:
                x_format = lambda x: x
                continue

            pivoted_and_ordered_df[col] = pivoted_and_ordered_df[col].apply(lambda x: GRADIENT_STR.replace("VALUE", x_format(x)).replace("MIN", str(min_values[col])).replace("MAX", str(max_values[col])).replace("MIDPOINT", str(0) if "rankwise" in col else str(round(midpoint[col], 1))))
    # Print or return your rearranged DataFrame
    print(pivoted_and_ordered_df)
    # add a column at the beginning that is empty
    pivoted_and_ordered_df.insert(0, "empty", "")
    
    pivoted_and_ordered_df.to_latex(os.path.join(args.results_dir, "all_results.tex"), index=False)
    print(f"Saved to {os.path.join(args.results_dir, 'all_results.tex')}")
    print(f"Saved to {os.path.join(args.results_dir, 'all_results.csv')}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results_dir", default="results", type=str)
    args = parser.parse_args()
    gather_results(args)
            