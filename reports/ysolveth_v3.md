# Ysolveth head v3 (MBPP+ outcome + bolt-style drafts)

Train 460 (MBPP+ 354 + bolt-style 106). Test 26 bolt-style prompts, never trained on.

Bolt-style labels are unreviewed drafts written by the assistant. Treat results as provisional.

## v3 (candidate)
accuracy: 0.923

```
              precision    recall  f1-score   support

        hard       0.92      0.92      0.92        13
    moderate       0.92      0.92      0.92        13
     trivial       0.00      0.00      0.00         0

    accuracy                           0.92        26
   macro avg       0.62      0.62      0.62        26
weighted avg       0.92      0.92      0.92        26

```
confusion (rows true hard/moderate, cols hard/moderate/trivial):
```
[[12  1  0]
 [ 1 12  0]
 [ 0  0  0]]
```

## v1 (current, baseline) on the same test set
accuracy: 0.577

```
[[9 4 0]
 [1 6 6]
 [0 0 0]]
```
