import mongoengine
import config
import models
from importlib import reload
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
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
    # subset the dataframe so it only includes t2 exercises
    df2 = df.loc[df["template"] == "t2_sleep_de_letters"]
    # add a final variable
    df2["behaviour_after_first_mistake"] = np.select(
        condlist = [
            df2.same_as_next.eq(1.0) & df2.action_after_first_mistake.eq("quit"),
            df2.same_as_next.eq(1.0) & df2.action_after_first_mistake.eq("continue") & df2.completed_float.eq(1.0),
            df2.same_as_next.eq(1.0) & df2.action_after_first_mistake.eq("continue") & df2.completed_float.eq(0.0),
            df2.same_as_next.eq(0.0) & df2.action_after_first_mistake.eq("quit"),
            df2.same_as_next.eq(0.0) & df2.action_after_first_mistake.eq("continue") & df2.completed_float.eq(1.0),
            df2.same_as_next.eq(0.0) & df2.action_after_first_mistake.eq("continue") & df2.completed_float.eq(0.0)
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
    return df2


def construct_dataset(ppids, data_type):
    """
    Takes a list of participant IDs 'ppids' and the 'data_type' to construct
    either the 'exercise' or 'letter'-based dataset from individual users' data.
    """
    df_all = pd.DataFrame()
    for pp in ppids:
        if data_type == "exercise":
            df_pp = process_exercises(pp)
        else:
            df_pp = pd.DataFrame()
        df_all = pd.concat([df_all, df_pp])
    return df_all


connection = mongoengine.connect(host=config.CONNECT_STR)
db = connection.get_database("progress")
participants = db.list_collection_names()

exercise_data = construct_dataset(participants, data_type="exercise")

exercise_data.plot(kind = 'scatter', x = 'exercise_number', y = 'num_mistakes')

plt.show()

mongoengine.disconnect()



def process_letters(exercise):
    """
    Takes a participant's exercise object and for each attempt at a letter
    collects relevant variables, which are returned as a dataframe.
    """
    # get response events while keeping track of original index
    action_events = [(num_i, i) for num_i, i in enumerate(exercise["events"], 0) if "action" in i]
    response_events = [i for i in action_events if i[1]["action"] == "attempt"]
    if len(response_events) == 0:
        return pd.DataFrame()
    # get audio events for later use
    audio_events = {str(num_i): i for num_i, i in enumerate(exercise["events"], 0) if i["event"] == "playAudio"}
    # get picture events for later use
    picture_events = {str(num_i): i for num_i, i in enumerate(exercise["events"], 0) if i["event"] == "showImage"}
    picture_ends = {i["uuid"]: float(i["time"]) for i in exercise["events"] if i["event"] == "hideImage" and i["uuid"] != ""}
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
        #"time_from_sound_between_answers": [],
        #"time_from_word_between_answers": [],
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
    for resp in response_events:
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
        words_betw_answers = []
        sounds_betw_answers = []
        n_word_betw_answers = 0
        n_sound_betw_answers = 0
        played_audio_indices = [int(i) for i in audio_events if int(i) > prev_resp_i and int(i) < resp[0]]
        for audio_i in played_audio_indices:
            audio_event = exercise["events"][audio_i]
            if audio_event["action"] == "play":             # if a word is played
                wrd_label = audio_event["audio"].split(".")[0]
                words_betw_answers.append(wrd_label)
                n_word_betw_answers += 1 if wrd_label == wrd else 0
                if wrd_label not in first_word_times:
                    first_word_times[wrd_label] = float(audio_event["time"])
            else:                                           # if a sound is played
                # get index of the sound and the word the sound belongs to
                sound_tpl = (audio_event["index"], audio_event["target"])
                sounds_betw_answers.append(str(sound_tpl))
                n_sound_betw_answers += 1 if sound_tpl[1] == wrd and sound_tpl[0] == pos else 0
                if str(sound_tpl) not in first_sound_times:
                    first_sound_times[str(sound_tpl)] = float(audio_event["time"])
        # look back for picture events between previous resp and current resp
        pics_betw_answers = []
        dur_pic_betw_answers = 0
        shown_picture_indices = [int(i) for i in picture_events if int(i) > prev_resp_i and int(i) < resp[0]]
        for pic_i in shown_picture_indices:
            pic_event = exercise["events"][pic_i]
            pic_label = pic_event["target"]
            pics_betw_answers.append(pic_label)
            if pic_event["uuid"] in picture_ends:
                pic_end = min(picture_ends[pic_event["uuid"]], float(resp[1]["time"]))             # make sure we use end time before response
            else:
                pic_end = float("nan")
            pic_dur = pic_end - float(pic_event["time"])
            dur_pic_betw_answers += pic_dur if pic_label == wrd else 0
            if pic_label not in first_pic_times:
                first_pic_times[pic_label] = float(pic_event["time"])
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
    #df[["word", "correct_letter", "chosen_letter", "words_played_between_answers", "time_from_first_word_audio_in_word_attempt"]]
    #df[["word", "correct_letter", "chosen_letter", "pictures_shown_between_answers", "time_from_first_picture_in_word_attempt"]]
    # derive more variables from initial variables
    df["num_attempts"] = df.groupby(["word", "position"]).cumcount() + 1
    df["prev_correct"] = df["correct"].shift()
    df["prev_letter_position"] = df["position"].shift()
    df["retry"] = np.where(df.prev_correct.eq("false") & df.prev_word.eq(df.word) & df.prev_letter_position.eq(df.position), "TRUE", "FALSE")
    df["right_to_left"] = np.select(
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
    results = db[ppid].find({"application": "t2_sleep_de_letters"}).sort("timestamp", 1)
    df_pp = pd.DataFrame()
    for result in results:
        df_exercise = process_letters(result)
        df_pp = pd.concat([df_pp, df_exercise])
    return df_pp





letter_data = construct_dataset(participants, data_type="letter")

letter_data["first_try_flt"] = np.where(letter_data.first_try.eq("TRUE"), 1.0, 0.0)

letter_bars = letter_data.groupby(["correct_letter"]).sum().first_try_flt / letter_data.groupby(["correct_letter"]).count().first_try

letter_bars.plot.bar()

plt.show()

letter_data_sub = letter_data.loc[letter_data["correct"] == "true"]

letter_bars_sub = letter_data_sub.groupby(["correct_letter"]).sum().first_try_flt / letter_data_sub.groupby(["correct_letter"]).count().first_try

letter_bars_sub.plot.bar()
plt.show()
