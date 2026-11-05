# Ysolveth head v5 candidate (rubric v1, task-level split)

Bolt-style records: 201. Tasks: 157 (train 125, test 32), split seed 42.
Train: MBPP+ 354 + bolt-style 159. Test: bolt-style 42.
Test label counts: {'moderate': 15, 'hard': 13, 'trivial': 14}

## v5 candidate
```
              precision    recall  f1-score   support

        hard       0.79      0.85      0.81        13
    moderate       0.83      0.67      0.74        15
     trivial       0.81      0.93      0.87        14

    accuracy                           0.81        42
   macro avg       0.81      0.81      0.81        42
weighted avg       0.81      0.81      0.81        42

```
confusion (rows true hard/moderate/trivial):
```
[[11  2  0]
 [ 2 10  3]
 [ 1  0 13]]
```
HARD routed to a lower tier: 2 of 13

## v1 current, same test set
```
              precision    recall  f1-score   support

        hard       0.62      0.62      0.62        13
    moderate       0.64      0.47      0.54        15
     trivial       0.67      0.86      0.75        14

    accuracy                           0.64        42
   macro avg       0.64      0.65      0.63        42
weighted avg       0.64      0.64      0.63        42

```
confusion (rows true hard/moderate/trivial):
```
[[ 8  4  1]
 [ 3  7  5]
 [ 2  0 12]]
```
HARD routed to a lower tier: 5 of 13

