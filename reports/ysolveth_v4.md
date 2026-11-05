# Ysolveth head v4 candidate (rubric v1, family-level split)

Included bolt-style records: 189. Excluded: {}.

Split seed 14. Test families: ['add end-to-end', 'add form', 'add sorting', 'center the', 'create a', 'integrate stripe', 'make the', 'swap the'].
Train: MBPP+ 354 + bolt-style 140. Test: bolt-style 49.

## v4 candidate
```
              precision    recall  f1-score   support

        hard       1.00      1.00      1.00        10
    moderate       0.79      1.00      0.88        23
     trivial       1.00      0.62      0.77        16

    accuracy                           0.88        49
   macro avg       0.93      0.88      0.88        49
weighted avg       0.90      0.88      0.87        49

```
confusion (rows true hard/moderate/trivial):
```
[[10  0  0]
 [ 0 23  0]
 [ 0  6 10]]
```
HARD routed to a lower tier: 0 of 10

## v1 current, same test set
```
              precision    recall  f1-score   support

        hard       0.54      0.70      0.61        10
    moderate       0.79      0.48      0.59        23
     trivial       0.68      0.94      0.79        16

    accuracy                           0.67        49
   macro avg       0.67      0.71      0.66        49
weighted avg       0.70      0.67      0.66        49

```
confusion:
```
[[ 7  3  0]
 [ 5 11  7]
 [ 1  0 15]]
```
HARD routed to a lower tier: 3 of 10
