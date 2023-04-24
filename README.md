# diglinplus
Scripts for DigLin+ data processing and analysis

## Instructions
- Clone this repo `git clone git@github.com:timjzee/diglinplus.git`
- `pip install -r requirements.txt` in a virtual environment
- Ask the project supervisor for the connection string and create a `.env` file:
```
# MongoDB connection string
CONNECT_STR=mongodb://yourconnectionstring
```
- If you want to continue development of this repo you should probably get a local copy of the database, so you're not constantly pulling the entire database over the internet:
    - start local mongodb server `brew services start mongodb-community@6.0`
    - `mongodump --uri "mongodb://yourconnectionstring" --out "/path/to/databaseDump"`
    - `mongorestore --db progress /path/to/databaseDump/progress`
    - don't forget to change `.env` file: `CONNECT_STR=mongodb://localhost:27017/progress` (27017 is the default port)
- now you can run `diglin.py`

## Codebooks

### exercise_data.csv

#### Description
Every row represents 1 attempt at an exercise within any of the templates. This dataset can be used to answer the following (and many other) questions:
- How many times is this template used before it is done without errors?
- Does the learner start again as soon as he makes a mistake?

In R:
```R
d <- read.csv("exercise_data.csv")
# Question 1
hist(d[(is.na(d$times_previously_correct) | d$times_previously_correct == 0) & d$correct == 1, ]$times_previously_attempted, breaks=100)
# Question 2
table(d$behaviour_after_first_mistake)
```

#### Columns
| Name                          | Description                                                                                           | Example |
| ---                           | ---                                                                                                   | --- |
| user_id                       | User identifier in the MongoDB database.                                                              | f3039b2f-5864-44cd-8e22-c16072f1e1d3@nt2school |
| exercise_id                   | Exercise identifier. Exercises are generated for each attempt, so every row has a different value.    | 63638bf2979071375ca6da7d |
| template                      | Name of the DigLin Template. Placeholder in case the dataset is extended to other Templates.          | t2_sleep_de_letters |
| start_time                    | Time when the exercise page was first displayed.                                                      | 2022-11-03T09:37:54.301Z |
| word_list                     | Name of the DigLin word list.                                                                         | Lijst 16  - ch - x - c |
| completed                     | Indicates whether the user completed the exercise attempt.                                            | True |
| completed_float               | See completed, but True = 1.0 and False = 0.0. Used to compute other variables.                       | 1.0 |
| duration                      | Time in seconds from the start of the exercise until the exercise page was closed.                    | 59.721 |
| num_mistakes                  | Number of wrong answers given in the attempt.                                                         | 5.0 |
| action_after_first_mistake    | Encodes whether a user chose to immediately quit or continue after making their first mistake. A value of NA indicates no mistakes were made. | quit |
| exercise_number               | A user-specific number indicating how many attempts at any exercise (not just T2) the user had made at the time of the current attempt. | 106 |
| times_previously_attempted    | A user-specific number indicating how many times the user has previously attempted the current Template x Word List combination. | 0 |
| times_previously_completed    | A user-specific number indicating how many times the user has previously completed the current Template x Word List combination. Has a value of 0.0 if previously attempted but not completed, and an empty value if not previously attempted. | 2.0 |
| correct                       | Indicates whether the attempt was completed without mistakes.                                         | 0.0 |
| times_previously_correct      | A user-specific number indicating how many times the user has previously completed the current Template x Word List combination without mistakes. Has an empty value if not previously attempted. | 1.0 |
| time_previously_spent         | Cumulative duration (in seconds) previously spent by the user on the current Template x Word List combination. | 138.499 |
| same_as_prev                  | Indicates whether the current Template x Word List combination is identical to the Template x Word List combination of the previous attempt by the same user. | 0.0 |
| prec_consec_attempts          | Indicates how many times the user had consecutively attempted the current Template x Word List combination immediately preceding the current attempt. | 4.0 |
| same_as_next                  | Indicates whether the current Template x Word List combination is identical to the Template x Word List combination of the next attempt by the same user. | 1.0 |
| behaviour_after_first_mistake | Combines information from action_after_first_mistake, same_as_next and completed_float as follows (in pseudo code): | |

```c++
if (same_as_next == true & action_after_first_mistake == "quit") {
    behaviour_after_first_mistake = "retry"
} else if (same_as_next == true & action_after_first_mistake == "continue" & completed_float = true) {
    behaviour_after_first_mistake = "finish & retry"
} else if (same_as_next == true & action_after_first_mistake == "continue" & completed_float = false) {
    behaviour_after_first_mistake = "continue & retry"
} else if (same_as_next == false & action_after_first_mistake == "quit") {
    behaviour_after_first_mistake = "move on"
} else if (same_as_next == false & action_after_first_mistake == "continue" & completed_float = true) {
    behaviour_after_first_mistake = "finish & move on"
} else if (same_as_next == false & action_after_first_mistake == "continue" & completed_float = false){
    behaviour_after_first_mistake = "continue & move on"
}
```

If no mistakes are made the value is *NA*.

### letter_data.csv

#### Description
Every row represents 1 attempt at a letter within Template 2 “Drag the letters”. This dataset can be used to answer the following (and many other) questions:
- Does the learner work from left to right?
- How much time is there between listening to the sound and finding the right letter? 
- Which letters are in the right place at once?

In R:
```R
d <- read.csv("letter_data.csv")
# Question 1
table(d$left_to_right)
# Question 2
hist(log(d[d$correct == "true",]$time_from_first_sound_audio_in_word_attempt), breaks = 100)
# Question 3
prop_first_try <- sapply(names(table(d$correct_letter)), function(x) sum(d[d$correct_letter == x,]$first_try_flt)) / table(d$correct_letter)
barplot(prop_first_try)
```

#### Columns
| Name                                          | Description                                                                                           | Example |
| ---                                           | ---                                                                                                   | --- |
| user_id                                       | User identifier in the MongoDB database.                                                              | f3039b2f-5864-44cd-8e22-c16072f1e1d3@nt2school |
| exercise_id                                   | Exercise identifier. Exercises are generated for each attempt, so every row has a different value.    | 63638bf2979071375ca6da7d |
| start_time                                    | Time when the exercise page was first displayed.                                                      | 2022-11-03T09:37:54.301Z |
| word_list                                     | Name of the DigLin word list.                                                                         | Lijst 16  - ch - x - c |
| word                                          | The word that the user is attempting to spell.                                                        | jurk |
| prev_word                                     | The word that the user was attempting to spell in the previous answer.                                | hek |
| correct_letter                                | The correct letter at the chosen position in the selected word.                                       | j |
| position                                      | The index of the chosen position in the word (starting from 0).                                       | 0 |
| chosen_letter                                 | The letter chosen by the user.                                                                        | e |
| correct                                       | Indicates whether the chosen_letter matches the correct_letter.                                       | false |
| word_attempt                                  | Identifies consecutive answers by the same user in the same exercise to the same word as belonging to the same word_attempt. When a user switches to a different word, word_attempt increments by 1. | 2 |
| answer_time                                   | Time (in ms) that has passed since the start of the exercise at the moment of the current answer.     | 11696.0 |
| words_played_between_answers                  | A semicolon-separated list of words of which the audio was played between the current answer and the previous answer. | jurk;hek |
| sounds_played_between_answers                 | A semicolon-separated list of sounds of which the audio was played between the current answer and the previous answer. Each sound is identified by the index of the sound and the word it belongs to. | ('1', 'want');('1', 'want') |
| times_word_played_between_answers             | Number of times the relevant word was played between answers.                                         | 0 |
| times_sound_played_between_answers            | Number of times the sound corresponding to the relevant position in the relevant word was played between answers. | 1 |
| words_played_between_words                    | A semicolon-separated list of words of which the audio was played between the first answer of the current word and the last answer to the previous word. | jurk;hek |
| sounds_played_between_words                   | A semicolon-separated list of sounds of which the audio was played between the first answer of the current word and the last answer to the previous word. Each sound is identified by the index of the sound and the word it belongs to. | ('1', 'want');('1', 'want') |
| times_word_played_between_words               | Number of times the relevant word was played between words.                                           | 2 |
| times_sound_played_between_words              | Number of times the sound corresponding to the first position in the relevant word was played between words. | 0 |
| time_from_first_sound_audio_in_word_attempt   | Time difference (in ms) between the current answer and the first time the relevant sound was played in the current word_attempt. | 2704.0 |
| time_from_first_word_audio_in_word_attempt    | Time difference (in ms) between the current answer and the first time the relevant word was played in the current word_attempt. | 8778.0 |
| pictures_shown_between_answers                | A semicolon-separated list of pictures that were shown between the current answer and the previous answer. | jurk;jurk |
| duration_picture_shown_between_answers        | Total duration (in ms) that the picture corresponding to the word was displayed between answers.      | 787.0 |
| pictures_shown_between_words                  | A semicolon-separated list of pictures that were shown between the first answer of the current word and the last answer to the previous word. | bed;bed;bed |
| duration_picture_shown_between_words          | Total duration (in ms) that the picture corresponding to the word was displayed between word attempts. | 1180.0 |
| time_from_first_picture_in_word_attempt       | Time difference (in ms) between the current answer and the the first time the relevant picture was shown in the current word_attempt. | 15503.0 |
| num_attempts                                  | Number of attempted answers at the current position in the current word at the time of the current attempt. | 2 |
| prev_correct                                  | Identifies if the previous answer (regardless of word_attempt) was correct. Empty valued if the current answer is the first answer of the exercise. | false |
| prev_letter_position                          | Gives the position of the previously answered letter. Empty valued if the current answer is the first answer of the exercise. | 3 |
| retry                                         | Indicates whether the current answer is an immediate retry of the incorrect previous answer.          | TRUE |
| first_try                                     | Indicates whether the user answered correctly in their first attempt.                                 | FALSE |
| first_try_flt                                 | See first_try. FALSE=0.0, TRUE=1.0.                                                                   | 0.0 |
| prev_letter                                   | Indicates the letter chosen in the previous answer.                                                   | u |
| same_letter_in_diff_word                      | Indicates whether a user, after answering a certain letter in a previous word, immediately answers that same letter in a different word. | TRUE |
| prev_time                                     | Time (in ms) that has passed since the start of the exercise at the moment of the previous answer.    | 11696.0 |
| answer_duration                               | Subtracts prev_time from answer_time to represent the time (in ms) it took the user to give the current answer. For the first answer, answer_duration equals answer_time. | 4070.0 |
| left_to_right                                 | Basically this variable indicates whether users work from left to right. Combines information from prev_letter_position, position, word, prev_word and retry as follows (in pseudo code): | |

```c++
if (postion == prev_letter_position + 1 & word == prev_word) {
    left_to_right = "TRUE"
} else if (retry == true | position == 0) {
    left_to_right = "NA"
} else {
    left_to_right = "FALSE"
}
```