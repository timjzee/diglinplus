import mongoengine
import config
import models
from importlib import reload
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
pd.set_option('display.max_rows', None)
pd.set_option('mode.chained_assignment', None)

# MongoDB collections represent users
# Objects within collections represent exercises
# events array within objects lists all actions within an exercise


def process_exercises(ppid):
    """
    Takes a participant ID (ppid) to retrieve that participant's exercises and
    returns a dataframe containing variables relevant to exercise-level
    questions.
    """
    config.col_name = ppid
    # we need to reload Exercise for each participant, because collection name changes
    reload(models)
    # update inheritance of collection
    collection = models.Exercise._get_collection()
    collection.update_many({'_cls': None}, {'$set': {'_cls': 'Exercise'}})
    results = models.Exercise.objects.order_by("+timestamp")
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


def process_letters(exercise):
    """
    Takes a participant's exercise object and for each attempt at a letter
    collects relevant variables, which are returned as a dataframe.
    """
    if len(exercise.response_events) == 0:
        return pd.DataFrame()
    # initialize dictionary
    d = {
        "user_id": [],
        "exercise_id": [],
        "start_time": [],
        "word_list": [],
        "word": [],
        "prev_word": [],
        "correct_letter": [],
        "position": [],
        "chosen_letter": [],
        "correct": [],
        "word_attempt": [],
        "answer_time": [],
        "words_played_between_answers": [],
        "sounds_played_between_answers": [],
        "times_word_played_between_answers": [],
        "times_sound_played_between_answers": [],
        "words_played_between_words": [],
        "sounds_played_between_words": [],
        "times_word_played_between_words": [],
        "times_sound_played_between_words": [],
        "time_from_first_sound_audio_in_word_attempt": [],        # in word attempt means that occurences of sound followed by sounds of a diff. word do not count)
        "time_from_first_word_audio_in_word_attempt": [],          # because users are not expect to retain this audio information in working memory
        "pictures_shown_between_answers": [],
        "duration_picture_shown_between_answers": [],
        "pictures_shown_between_words": [],
        "duration_picture_shown_between_words": [],
        "time_from_first_picture_in_word_attempt": []
    }
    # step through responses to collect data
    prev_resp_i = 0
    prev_wrd = "NA"
    words_betw_words = []
    sounds_betw_words = []
    n_word_betw_words = 0
    n_sound_betw_words = 0
    pics_betw_words = []
    dur_pic_betw_words = 0
    wrd_attempt = 0
    for resp_n, resp in enumerate(exercise.response_events, 0):
        d["user_id"].append(exercise["user"])
        d["exercise_id"].append(exercise["_id"].__str__())
        d["start_time"].append(exercise["timestamp"])
        d["word_list"].append(exercise["path"][2]["title"])
        wrd = resp[1]["parent"]
        d["word"].append(wrd)
        d["prev_word"].append(prev_wrd)
        d["correct_letter"].append(resp[1]["required"])
        pos = resp[1]["position"]
        d["position"].append(float(pos))
        d["chosen_letter"].append(resp[1]["givenAnswer"])
        d["correct"].append(resp[1]["correct"])
        if wrd != prev_wrd:
            wrd_attempt += 1
            first_sound_times = {}
            first_word_times = {}
            first_pic_times = {}
        d["word_attempt"].append(wrd_attempt)
        d["answer_time"].append(float(resp[1]["time"]))
        # look back for audio events between previous resp and current resp
        first_sound_times, first_word_times, words_betw_answers, sounds_betw_answers, n_word_betw_answers, n_sound_betw_answers = exercise.get_audio(first_sound_times, first_word_times, prev_resp_i, resp_n)
        # look back for picture events between previous resp and current resp
        first_pic_times, pics_betw_answers, dur_pic_betw_answers = exercise.get_pictures(first_pic_times, prev_resp_i, resp_n)
        # these variables are only updated between words
        if wrd != prev_wrd:
            words_betw_words = words_betw_answers
            sounds_betw_words = sounds_betw_answers
            n_word_betw_words = n_word_betw_answers
            n_sound_betw_words = n_sound_betw_answers
            pics_betw_words = pics_betw_answers
            dur_pic_betw_words = dur_pic_betw_answers
        # append audio related variables
        d["words_played_between_answers"].append(";".join(words_betw_answers))
        d["sounds_played_between_answers"].append(";".join(sounds_betw_answers))
        d["times_word_played_between_answers"].append(n_word_betw_answers)
        d["times_sound_played_between_answers"].append(n_sound_betw_answers)
        d["words_played_between_words"].append(";".join(words_betw_words))
        d["sounds_played_between_words"].append(";".join(sounds_betw_words))
        d["times_word_played_between_words"].append(n_word_betw_words)
        d["times_sound_played_between_words"].append(n_sound_betw_words)
        # append picture related variables
        d["pictures_shown_between_answers"].append(";".join(pics_betw_answers))
        d["duration_picture_shown_between_answers"].append(dur_pic_betw_answers)
        d["pictures_shown_between_words"].append(";".join(pics_betw_words))
        d["duration_picture_shown_between_words"].append(dur_pic_betw_words)
        # calculate and append times from sound to answer if applicable
        if str((pos, wrd)) in first_sound_times:
            d["time_from_first_sound_audio_in_word_attempt"].append(float(resp[1]["time"]) - first_sound_times[str((pos, wrd))])
        else:
            d["time_from_first_sound_audio_in_word_attempt"].append(float("nan"))
        if wrd in first_word_times:
            d["time_from_first_word_audio_in_word_attempt"].append(float(resp[1]["time"]) - first_word_times[wrd])
        else:
            d["time_from_first_word_audio_in_word_attempt"].append(float("nan"))
        # calculate and append times from picture to answer if applicable
        if wrd in first_pic_times:
            d["time_from_first_picture_in_word_attempt"].append(float(resp[1]["time"]) - first_pic_times[wrd])
        else:
            d["time_from_first_picture_in_word_attempt"].append(float("nan"))
        # update relevant variables for next response
        prev_resp_i = resp[0]
        prev_wrd = wrd
    # construct initial dataframe
    df = pd.DataFrame(d)
    # derive more variables from initial variables
    df["num_attempts"] = df.groupby(["word", "position"]).cumcount() + 1
    df["prev_correct"] = df["correct"].shift()
    df["prev_letter_position"] = df["position"].shift()
    df["retry"] = np.where(df.prev_correct.eq("false") & df.prev_word.eq(df.word) & df.prev_letter_position.eq(df.position), "TRUE", "FALSE")
    df["left_to_right"] = np.select(
        condlist=[
            df.position.eq(df.prev_letter_position + 1) & df.word.eq(df.prev_word),
            df.retry.eq("TRUE") | df.position.eq(0)
        ],
        choicelist=[
            "TRUE",
            "NA"
        ],
        default="FALSE"
    )
    #df[["word", "position", "correct_letter", "chosen_letter", "num_attempts", "retry", "right_to_left"]]
    df["first_try"] = np.where(df.num_attempts.eq(1) & df.correct.eq("true"), "TRUE", "FALSE")
    df["first_try_flt"] = np.where(df.first_try.eq("TRUE"), 1.0, 0.0)
    df["prev_letter"] = df["chosen_letter"].shift()
    df["same_letter_in_diff_word"] = np.where(df.prev_letter.eq(df.chosen_letter) & df.word.ne(df.prev_word), "TRUE", "FALSE")
    df["prev_time"] = df["answer_time"].shift()
    df["answer_duration"] = df["answer_time"] - df["prev_time"]
    df.loc[0, "answer_duration"] = df.loc[0, "answer_time"]
    return(df)


def get_letter_data(ppid):
    """
    Takes a participant ID (ppid) to retrieve that participant's T2 exercises
    and returns a dataframe containing variables relevant to letter-level
    questions.
    """
    config.col_name = ppid
    # we need to reload Exercise for each participant, because collection name changes
    reload(models)
    collection = models.Exercise._get_collection()
    collection.update_many({'_cls': None}, {'$set': {'_cls': 'Exercise'}})
    results = models.Exercise.objects(application="t2_sleep_de_letters").order_by("+timestamp")
    df_pp = pd.DataFrame()
    for result in results:
        # create T2 result to add T2-specific methods
        t2_result = models.ExerciseT2(**result.to_mongo())
        # process it
        df_exercise = process_letters(t2_result)
        df_pp = pd.concat([df_pp, df_exercise])
    return df_pp


def process_bingo(exercise):
    """
    Takes a participant's exercise object and for each attempt at a word
    collects relevant variables, which are returned as a dataframe.
    """
    if len(exercise.response_events) == 0:
        return pd.DataFrame()
    # initialize dictionary
    d = {
        "user_id": [],
        "exercise_id": [],
        "exercise_time": [],
        "start_time": [],
        "word_list": [],
        "word": [],
        "word_answer": [],
        "word_attempt": [],
        "correct": [],
        #"words_played_between_answers": [],
        #"words_played_between_words": [],
        "times_word_played_between_answers": [],
        "times_word_played_between_words": [],
        "answer_time": [],
        "time_from_first_word_audio_in_word_attempt": []
    }
    # step through responses to collect data
    prev_resp_i = 0
    prev_wrd = "NA"
    words_betw_words = []
    n_word_betw_words = 0
    wrd_attempt = 0
    for resp_n, resp in enumerate(exercise.response_events, 0):
        d["user_id"].append(exercise["user"])
        d["exercise_id"].append(exercise["_id"].__str__())
        d["exercise_time"].append(exercise["timestamp"])
        d["start_time"].append(exercise.get_start())
        d["word_list"].append(exercise["path"][2]["title"])
        wrd = resp[1]["parent"]
        d["word"].append(wrd)
        d["word_answer"].append(resp[1]["givenAnswer"])
        d["correct"].append(resp[1]["correct"])
        if wrd != prev_wrd:
            wrd_attempt += 1
            first_word_times = {}
        d["word_attempt"].append(wrd_attempt)
        d["answer_time"].append(float(resp[1]["time"]))
        # look back for audio events between previous resp and current resp
        first_word_times, words_betw_answers, n_word_betw_answers = exercise.get_audio(first_word_times, prev_resp_i, resp_n)
        # We assume that the audio is automatically played if the answer is incorrect
        if resp[1]["correct"] == "false":
            n_word_betw_answers += 1
        # these variables are only updated between words
        if wrd != prev_wrd:
            words_betw_words = words_betw_answers
            n_word_betw_words = n_word_betw_answers
        # append audio related variables
        #d["words_played_between_answers"].append(";".join(words_betw_answers))
        d["times_word_played_between_answers"].append(n_word_betw_answers)
        #d["words_played_between_words"].append(";".join(words_betw_words))
        d["times_word_played_between_words"].append(n_word_betw_words)
        # calculate and append times from audio to answer if applicable
        if wrd in first_word_times:
            d["time_from_first_word_audio_in_word_attempt"].append(float(resp[1]["time"]) - first_word_times[wrd])
        else:
            d["time_from_first_word_audio_in_word_attempt"].append(float("nan"))
        # update relevant variables for next response
        prev_resp_i = resp[0]
        prev_wrd = wrd
    # construct initial dataframe
    df = pd.DataFrame(d)
    # derive more variables from initial variables
    df["num_attempts"] = df.groupby(["word"]).cumcount() + 1
    df["prev_correct"] = df["correct"].shift()
    df["first_try"] = np.where(df.num_attempts.eq(1) & df.correct.eq("true"), "TRUE", "FALSE")
    df["first_try_flt"] = np.where(df.first_try.eq("TRUE"), 1.0, 0.0)
    df["prev_time"] = df["answer_time"].shift()
    df["answer_duration"] = df["answer_time"] - df["prev_time"]
    df.loc[0, "answer_duration"] = df.loc[0, "answer_time"] - float(df.loc[0, "start_time"])
    return(df)


def get_bingo_data(ppid):
    """
    Takes a participant ID (ppid) to retrieve that participant's T5 exercises
    and returns a dataframe containing variables relevant to letter-level
    questions.
    """
    config.col_name = ppid
    # we need to reload Exercise for each participant, because collection name changes
    reload(models)
    collection = models.Exercise._get_collection()
    collection.update_many({'_cls': None}, {'$set': {'_cls': 'Exercise'}})
    results = models.Exercise.objects(application="bingo_v2").order_by("+timestamp")
    df_pp = pd.DataFrame()
    for result in results:
        # create T5 result to add T5-specific methods
        t5_result = models.ExerciseT5(**result.to_mongo())
        # process it
        df_exercise = process_bingo(t5_result)
        df_pp = pd.concat([df_pp, df_exercise])
    return df_pp


def construct_dataset(ppids, data_type):
    """
    Takes a list of participant IDs 'ppids' and the 'data_type' to construct
    either the 'exercise' or 'letter'-based dataset from individual users' data.
    """
    df_all = pd.DataFrame()
    for pp in ppids:
        if data_type == "exercise":
            df_pp = process_exercises(pp)
        elif data_type == "t2":
            df_pp = get_letter_data(pp)
        elif data_type == "t5":
            df_pp = get_bingo_data(pp)
        df_all = pd.concat([df_all, df_pp])
    return df_all


connection = mongoengine.connect(host=config.CONNECT_STR)
db = connection.get_database("progress")
participants = db.list_collection_names()

# test exercise data

exercise_data = construct_dataset(participants, data_type="exercise")

exercise_data.plot(kind = 'scatter', x = 'exercise_number', y = 'num_mistakes')

plt.show()

exercise_data.to_csv("exercise_data.csv")


# test letter data

letter_data = construct_dataset(participants, data_type="t2")

letter_bars = letter_data.groupby(["correct_letter"]).sum().first_try_flt / letter_data.groupby(["correct_letter"]).count().first_try

letter_bars.plot.bar()

plt.show()

letter_data_sub = letter_data.loc[letter_data["correct"] == "true"]

letter_bars_sub = letter_data_sub.groupby(["correct_letter"]).sum().first_try_flt / letter_data_sub.groupby(["correct_letter"]).count().first_try

letter_bars_sub.plot.bar()
plt.show()

letter_data.to_csv("letter_data.csv")


# test bingo data

bingo_data = construct_dataset(participants, data_type="t5")

bingo_data.to_csv("/Users/tim/Documents/diglinplus/bingo_data.csv")

mongoengine.disconnect()