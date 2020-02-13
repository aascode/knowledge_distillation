import json
import os

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, accuracy_score
from sklearn.model_selection import train_test_split
from tensorflow.keras.callbacks import ModelCheckpoint, EarlyStopping, ReduceLROnPlateau

from model import get_model, get_kd_model


def gen(X, Y, batch_size=64):
    indexes = list(range(X.shape[0]))
    while True:
        batch_indexes_1 = np.random.choice(indexes, size=batch_size).tolist()
        batch_indexes_2 = np.random.choice(indexes, size=batch_size).tolist()
        alphas = np.random.uniform(0, 1, size=batch_size).tolist()

        X_1 = [X[i, ...] for i in batch_indexes_1]
        X_2 = [X[i, ...] for i in batch_indexes_2]

        Y_1 = [Y[i, ...] for i in batch_indexes_1]
        Y_2 = [Y[i, ...] for i in batch_indexes_2]

        X_batch = [l * a + (1 - l) * b for a, b, l in zip(X_1, X_2, alphas)]

        Y_batch = [l * a + (1 - l) * b for a, b, l in zip(Y_1, Y_2, alphas)]

        yield np.array(X_batch), np.array(Y_batch)


if __name__ == "__main__":
    file_path_source = "baseline.h5"
    file_path_kd = "kd.h5"

    df_train = pd.read_csv("../input/mitbih_train.csv", header=None)
    df = pd.read_csv("../input/mitbih_test.csv", header=None)

    df_test, df_val = train_test_split(df, test_size=0.2, random_state=1337)

    Y_train = np.array(df_train[187].values).astype(np.int8)
    X_train = np.array(df_train[list(range(187))].values)[..., np.newaxis]

    Y_val = np.array(df_val[187].values).astype(np.int8)
    X_val = np.array(df_val[list(range(187))].values)[..., np.newaxis]

    Y_test = np.array(df_test[187].values).astype(np.int8)
    X_test = np.array(df_test[list(range(187))].values)[..., np.newaxis]

    model_source = get_model()
    model_source.load_weights(file_path_source)
    Y_train_pred = model_source.predict(X_train)
    Y_val_pred = model_source.predict(X_val)

    model = get_kd_model()

    checkpoint = ModelCheckpoint(file_path_kd, monitor='val_loss', verbose=1, save_best_only=True, mode="min")
    reduce = ReduceLROnPlateau(monitor="val_loss", patience=10, min_lr=1e-7, mode="min")
    early = EarlyStopping(monitor="val_loss", patience=30, mode="min")

    model.fit_generator(gen(X_train, Y_train_pred, batch_size=64),
                        validation_data=gen(X_val, Y_val_pred, batch_size=64),
                        epochs=1000, verbose=1, callbacks=[checkpoint, reduce, early],
                        steps_per_epoch=X_train.shape[0]//64, validation_steps=X_val.shape[0]//64)

    pred_test = model.predict(X_test)
    pred_test = np.argmax(pred_test, axis=-1)

    f1 = f1_score(Y_test, pred_test, average="macro")

    acc = accuracy_score(Y_test, pred_test)

    print("acc :", acc)
    print("f1 :", f1)

    rnd = np.random.randint(1, 100000)
    os.makedirs('../output/ecg/', exist_ok=True)

    with open('../output/ecg/kd_performance_%s.json' % int(rnd), 'w') as f:
        json.dump({"acc": acc, "f1": f1}, f, indent=4)