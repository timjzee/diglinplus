import mongoengine
import config
import models
from importlib import reload
import numpy as np
import pandas as pd
pd.set_option('display.max_rows', None)
pd.set_option('mode.chained_assignment', None)


class DataExercise:
    def __init__(self):
        self.df = pd.DataFrame()
        self.regex_pattern = ".*"
    
    def save(self, filename):
        self.df.to_csv(filename, index=False)

    def load(self, filename):
        self.df = pd.read_csv(filename)

    def construct(self, ppids):
        """
        Takes a list of participant IDs 'ppids' to construct
        the dataset from individual users' data.
        """
        for ppid in ppids:
            config.col_name = ppid
            # we need to reload Exercise for each participant, because collection name changes
            reload(models)
            # update inheritance of collection
            collection = models.Exercise._get_collection()
            collection.update_many({'_cls': None}, {'$set': {'_cls': 'Exercise'}})
            results = models.Exercise.objects(mongoengine.Q(application__contains=self.regex_pattern)).order_by("+timestamp")
            df_pp = self.process_data(results)
            self.df = pd.concat([self.df, df_pp])
    
    def process_data(self, results):
        """
        Takes a participant's exercises and
        returns a dataframe containing variables relevant to exercise-level
        questions.
        """
        # initialize dictionary
        d = {
            "user_id": [],
            "exercise_id": [],
            "template": [],
            "start_time": [],
            "word_list": [],
            "completed": [],
            "duration": [],
            "num_mistakes": [],
            "action_after_first_mistake": []
        }
        # step through
        for result in results:
            # skip if eventlog is empty
            if len([i for i in result["events"] if i["event"] != "close"]) == 0:
                continue
            d["user_id"].append(result["user"])
            d["exercise_id"].append(result["_id"].__str__())
            d["start_time"].append(result["timestamp"])
            d["word_list"].append(result["path"][2]["title"])
            d["template"].append(result["application"])
            d["duration"].append(result.return_duration())
            d["completed"].append(result.return_complete())
            n_mistakes, action = result.return_mistakes()
            d["num_mistakes"].append(n_mistakes)
            d["action_after_first_mistake"].append(action)
        # construct the initial dataframe
        df = pd.DataFrame(d)
        # Add some more variables based on initial variables
        df["exercise_number"] = range(1, df.shape[0] + 1)
        df["times_previously_attempted"] = df.groupby(["template", "word_list"]).cumcount()
        df["completed_float"] = df["completed"].astype(float)
        df["times_previously_completed"] = df.groupby(["template", "word_list"], group_keys=False)["completed_float"].apply(lambda x : x.shift().cumsum())
        df["correct"] = df["num_mistakes"].apply(lambda x : 1.0 if x == 0 else 0.0 if x > 0 else float("nan")) * df["completed_float"]
        df["times_previously_correct"] = df.groupby(["template", "word_list"], group_keys=False)["correct"].apply(lambda x: x.shift().cumsum())
        df["time_previously_spent"] = df.groupby(["template", "word_list"], group_keys=False)["duration"].apply(lambda x : x.shift().cumsum())
        df["time_previously_spent"] = df["time_previously_spent"].fillna(0)
        df["same_as_prev"] = pd.Series([1.0]*df.shape[0]).where((df["template"] == df["template"].shift()) & (df["word_list"] == df["word_list"].shift()), 0.0)
        df["prec_consec_attempts"] = df["same_as_prev"]
        for i in range(1, len(df)):
            df.loc[i, "prec_consec_attempts"] = df.loc[i, "prec_consec_attempts"] * (df.loc[i-1, "prec_consec_attempts"] + df.loc[i, "prec_consec_attempts"])
        df["same_as_next"] = df["same_as_prev"].shift(-1)
        # add a final variable for T2
        df["behaviour_after_first_mistake"] = np.select(
            condlist = [
                df.same_as_next.eq(1.0) & df.action_after_first_mistake.eq("quit"),
                df.same_as_next.eq(1.0) & df.action_after_first_mistake.eq("continue") & df.completed_float.eq(1.0),
                df.same_as_next.eq(1.0) & df.action_after_first_mistake.eq("continue") & df.completed_float.eq(0.0),
                df.same_as_next.eq(0.0) & df.action_after_first_mistake.eq("quit"),
                df.same_as_next.eq(0.0) & df.action_after_first_mistake.eq("continue") & df.completed_float.eq(1.0),
                df.same_as_next.eq(0.0) & df.action_after_first_mistake.eq("continue") & df.completed_float.eq(0.0)
            ],
            choicelist = [
                "retry",
                "finish & retry",
                "continue & retry",
                "move on",
                "finish & move on",
                "continue & move on"
            ],
            default="NA"
        )
        # resulting warning can be silenced with: pd.options.mode.chained_assignment = None
        # return the participants dataframe
        return df