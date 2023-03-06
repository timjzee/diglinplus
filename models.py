import mongoengine
import config

class Exercise(mongoengine.Document):
    meta = {'collection': config.col_name}
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
    # some variables have only been tested for t2, so we ignore other templates
    def return_complete(self):
        if self.application == "t2_sleep_de_letters":
            return "completed" in [i["event"] for i in self.events]
        else:
            return float("nan")
    def return_mistakes(self):
        if self.application == "t2_sleep_de_letters":
            self.attempts = [i["correct"] for i in self.events if "givenAnswer" in i]
            self.n_mistakes = sum([int(i=='false') for i in self.attempts])
            self.first_mistake_i = float("nan") if "false" not in self.attempts else self.attempts.index("false")
            self.action = "quit" if self.first_mistake_i + 1 == len(self.attempts) else "continue" if self.first_mistake_i + 1 < len(self.attempts) else "NA"
            return self.n_mistakes, self.action
        else:
            return float("nan"), "NA"
    def return_duration(self):
        return float([i for i in self.events if i["event"] != "close"][-1]["time"]) / 1000
