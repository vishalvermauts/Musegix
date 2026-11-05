# Ysolveth head v2 (MBPP+ outcome labels)

Train 283 / test 71 (split by prompt, stratified, seed 42).

```
              precision    recall  f1-score   support

        hard       0.00      0.00      0.00         1
    moderate       0.08      0.14      0.11         7
     trivial       0.90      0.83      0.86        63

    accuracy                           0.75        71
   macro avg       0.33      0.32      0.32        71
weighted avg       0.80      0.75      0.77        71

```

Confusion matrix (rows = true hard/moderate/trivial):

```
[[ 0  0  1]
 [ 1  1  5]
 [ 0 11 52]]
```
