import mongoengine
import config

class Exercise(mongoengine.Document):
    meta = {'collection': config.col_name, 'allow_inheritance': True}
    _id = mongoengine.ObjectIdField()
    user = mongoengine.StringField()
    progress = mongoengine.StringField()
    path = mongoengine.ListField()
    exercise = mongoengine.StringField()
    title = mongoengine.StringField()
    menu = mongoengine.StringField()
    application = mongoengine.StringField()
    language = mongoengine.StringField()
    timestamp = mongoengine.StringField()
    events = mongoengine.ListField()
    
    # some methods do not not apply to t1
    def return_complete(self):
        if self.application == "t1_de_woorden":
            return float("nan")
        return "completed" in [i["event"] for i in self.events]

    def return_mistakes(self):
        if self.application == "t1_de_woorden":
            return float("nan"), "NA"
        self.attempts = [i["correct"] for i in self.events if "givenAnswer" in i]
        self.n_mistakes = sum([int(i=='false') for i in self.attempts])
        self.first_mistake_i = float("nan") if "false" not in self.attempts else self.attempts.index("false")
        self.action = "quit" if self.first_mistake_i + 1 == len(self.attempts) else "continue" if self.first_mistake_i + 1 < len(self.attempts) else "NA"
        return self.n_mistakes, self.action

    def return_duration(self):
        return float([i for i in self.events if i["event"] != "close"][-1]["time"]) / 1000


class ExerciseT2(Exercise):
    """Sub-class of Exercise that adds methods for analyzing Template 2 data."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # get response events while keeping track of original index
        self.action_events = [(num_i, i) for num_i, i in enumerate(self.events, 0) if "action" in i]
        self.response_events = [i for i in self.action_events if i[1]["action"] == "attempt"]
        # get audio events for later use
        self.audio_events = {str(num_i): i for num_i, i in enumerate(self.events, 0) if i["event"] == "playAudio"}
        # get picture events for later use
        self.picture_events = {str(num_i): i for num_i, i in enumerate(self.events, 0) if i["event"] == "showImage"}
        self.picture_ends = {i["uuid"]: float(i["time"]) for i in self.events if i["event"] == "hideImage" and i["uuid"] != ""}

    def get_audio(self, first_sound_times, first_word_times, prev_resp_i, resp_n):
        """look back for audio events between previous resp and current resp"""
        resp = self.response_events[resp_n]
        wrd = resp[1]["parent"]
        pos = resp[1]["position"]
        words_betw_answers = []
        sounds_betw_answers = []
        n_word_betw_answers = 0
        n_sound_betw_answers = 0
        played_audio_indices = [int(i) for i in self.audio_events if int(i) > prev_resp_i and int(i) < resp[0]]
        for audio_i in played_audio_indices:
            audio_event = self.events[audio_i]
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
        return first_sound_times, first_word_times, words_betw_answers, sounds_betw_answers, n_word_betw_answers, n_sound_betw_answers
    
    def get_pictures(self, first_pic_times, prev_resp_i, resp_n):
        """look back for picture events between previous resp and current resp"""
        resp = self.response_events[resp_n]
        wrd = resp[1]["parent"]
        pics_betw_answers = []
        dur_pic_betw_answers = 0
        shown_picture_indices = [int(i) for i in self.picture_events if int(i) > prev_resp_i and int(i) < resp[0]]
        for pic_i in shown_picture_indices:
            pic_event = self.events[pic_i]
            pic_label = pic_event["target"]
            pics_betw_answers.append(pic_label)
            if pic_event["uuid"] in self.picture_ends:
                pic_end = min(self.picture_ends[pic_event["uuid"]], float(resp[1]["time"]))             # make sure we use end time before response
            else:
                pic_end = float("nan")
            pic_dur = pic_end - float(pic_event["time"])
            dur_pic_betw_answers += pic_dur if pic_label == wrd else 0
            if pic_label not in first_pic_times:
                first_pic_times[pic_label] = float(pic_event["time"])
        return first_pic_times, pics_betw_answers, dur_pic_betw_answers
    

class ExerciseT5(Exercise):
    """Sub-class of Exercise that adds methods for analyzing Template 5 (bingo) data."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # get response events while keeping track of original index
        self.action_events = [(num_i, i) for num_i, i in enumerate(self.events, 0) if "action" in i]
        self.response_events = [i for i in self.action_events if i[1]["action"] == "attempt"]
        # get audio events for later use
        self.audio_events = {str(num_i): i for num_i, i in enumerate(self.events, 0) if i["event"] == "playAudio"}
    
    def get_start(self):
        "Return when the start button was clicked."
        if len([i for i in self.events if i["event"] == "start"]) > 0:
            return [i for i in self.events if i["event"] == "start"][0]["time"]
        else:
            return "nan"
    
    def get_audio(self, first_word_times, prev_resp_i, resp_n):
        """look back for audio events between previous resp and current resp"""
        resp = self.response_events[resp_n]
        wrd = resp[1]["parent"]
        words_betw_answers = []
        n_word_betw_answers = 0
        played_audio_indices = [int(i) for i in self.audio_events if int(i) > prev_resp_i and int(i) < resp[0]]
        for audio_i in played_audio_indices:
            audio_event = self.events[audio_i]
            wrd_label = audio_event["target"]
            words_betw_answers.append(wrd_label)
            n_word_betw_answers += 1 if wrd_label == wrd else 0
            if wrd_label not in first_word_times:
                first_word_times[wrd_label] = float(audio_event["time"])

        return first_word_times, words_betw_answers, n_word_betw_answers


class ExerciseT3(ExerciseT2):
    """
    Sub-class of Exercise that adds methods for analyzing Template 3 (drag the words) data.
    It inherits from ExerciseT2, overwrites its get_audio method and adds get_start functionality.
    """
    
    def get_start(self):
        "Return when the start button was clicked."
        if len([i for i in self.events if i["event"] == "start"]) > 0:
            return [i for i in self.events if i["event"] == "start"][0]["time"]
        else:
            return "nan"
    
    def get_audio(self, first_word_times, prev_resp_i, resp_n):
        """look back for audio events between previous resp and current resp"""
        resp = self.response_events[resp_n]
        wrd = resp[1]["parent"]
        words_betw_answers = []
        sounds_betw_answers = []
        n_word_betw_answers = 0
        played_audio_indices = [int(i) for i in self.audio_events if int(i) > prev_resp_i and int(i) < resp[0]]
        for audio_i in played_audio_indices:
            audio_event = self.events[audio_i]
            if audio_event["action"] == "playWord":             # if a word is played
                wrd_label = audio_event["audio"].split(".")[0]
                words_betw_answers.append(wrd_label)
                n_word_betw_answers += 1 if wrd_label == wrd else 0
                if wrd_label not in first_word_times:
                    first_word_times[wrd_label] = float(audio_event["time"])
            else:                                           # if a sound from the soundbar is played
                assert audio_event["action"] == "soundbarSound"
                # get index of the sound and the word the sound belongs to
                # get sound label
                sound_lab = audio_event["audio"]
                sounds_betw_answers.append(str(sound_lab))
        
        return first_word_times, words_betw_answers, sounds_betw_answers, n_word_betw_answers
    

class ExerciseT4(ExerciseT2):
    """
    Sub-class of Exercise that adds methods for analyzing Template 4 (form the words) data.
    It inherits from ExerciseT2, overwrites its get_audio method and adds get_start functionality.
    """

    def get_start(self):
        "Return when the start button was clicked."
        if len([i for i in self.events if i["event"] == "start"]) > 0:
            return [i for i in self.events if i["event"] == "start"][0]["time"]
        else:
            return "nan"
        
    def get_audio(self, first_sound_times, prev_resp_i, resp_n):
        """look back for audio events between previous resp and current resp"""
        resp = self.response_events[resp_n]
        wrd = resp[1]["parent"]
        words_betw_answers = []
        sounds_betw_answers = []
        sb_sounds_betw_answers = []
        audio_betw_answers = []
        n_sound_betw_answers = 0
        n_sb_sound_betw_answers = 0
        played_audio_indices = [int(i) for i in self.audio_events if int(i) > prev_resp_i and int(i) < resp[0]]
        for audio_i in played_audio_indices:
            audio_event = self.events[audio_i]
            if audio_event["action"] == "playWord":             # if a word is played
                wrd_label = audio_event["audio"].split(".")[0]
                words_betw_answers.append(wrd_label)
                audio_betw_answers.append(wrd_label)
            elif audio_event["action"] == "character_sound":         # if a sound is played
                # get index of the sound and the word the sound belongs to
                sound_tpl = (audio_event["index"], audio_event["target"])
                sounds_betw_answers.append(str(sound_tpl))
                audio_betw_answers.append(str(sound_tpl))
                n_sound_betw_answers += 1 if sound_tpl[1] == wrd else 0
                if str(sound_tpl) not in first_sound_times:
                    first_sound_times[str(sound_tpl)] = float(audio_event["time"])
            else:                                                       # if a soundbarSound is played
                sb_sound_tpl = (audio_event["audio"], "soundbar")
                sb_sounds_betw_answers.append(str(sb_sound_tpl))
                audio_betw_answers.append(str(sb_sound_tpl))
                n_sb_sound_betw_answers += 1
        
        return first_sound_times, audio_betw_answers, n_sound_betw_answers