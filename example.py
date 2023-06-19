import config
import mongoengine
from data import DataExercise, DataT2, DataT3, DataT5
import matplotlib.pyplot as plt


connection = mongoengine.connect(host=config.CONNECT_STR)
db = connection.get_database("progress")
participants = db.list_collection_names()

# exercise data

# constructing from MongoDB
exercise_data = DataExercise()
exercise_data.construct(participants)

# saving and loading
exercise_data.save("exercise_data_test.csv")
exercise_data = DataExercise()
exercise_data.df
exercise_data.load("exercise_data_test.csv")

# visualize some data
exercise_data.df.plot(kind = 'scatter', x = 'exercise_number', y = 'num_mistakes')
plt.show()

# letter data
letter_data = DataT2()
letter_data.construct(participants)
letter_bars = letter_data.df.groupby(["correct_letter"]).sum().first_try_flt / letter_data.df.groupby(["correct_letter"]).count().first_try
letter_bars.plot.bar()
plt.show()

# bingo data
bingo_data = DataT5()
bingo_data.construct(participants)
bingo_data.save("bingo_data_test.csv")

# drag_words data
dw_data = DataT3()
dw_data.construct(participants)
dw_data.save("drag_words_data.csv")


mongoengine.disconnect()