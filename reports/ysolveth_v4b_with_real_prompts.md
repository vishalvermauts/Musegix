# Ysolveth head v4 candidate (rubric v1, family-level split)

Included bolt-style records: 201. Excluded: {}.

Split seed 26. Test families: ['change the', 'create a', 'implement optimistic', 'implement undo', 'reduce the'].
Train: MBPP+ 354 + bolt-style 136. Test: bolt-style 65.

## v4 candidate
```
              precision    recall  f1-score   support

        hard       0.89      0.89      0.89         9
    moderate       0.37      0.95      0.54        20
     trivial       1.00      0.14      0.24        36

    accuracy                           0.49        65
   macro avg       0.75      0.66      0.56        65
weighted avg       0.79      0.49      0.42        65

```
confusion (rows true hard/moderate/trivial):
```
[[ 8  1  0]
 [ 1 19  0]
 [ 0 31  5]]
```
HARD routed to a lower tier: 1 of 9

## v1 current, same test set
```
              precision    recall  f1-score   support

        hard       0.46      0.67      0.55         9
    moderate       0.79      0.55      0.65        20
     trivial       0.84      0.89      0.86        36

    accuracy                           0.75        65
   macro avg       0.70      0.70      0.69        65
weighted avg       0.77      0.75      0.75        65

```
confusion:
```
[[ 6  2  1]
 [ 4 11  5]
 [ 3  1 32]]
```
HARD routed to a lower tier: 3 of 9
