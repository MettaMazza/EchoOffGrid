#include <Python.h>
#include <jni.h>
#include <stdlib.h>

JNIEXPORT jint JNICALL Java_dev_echooffgrid_mobile_Main_start(
        JNIEnv *env, jclass type, jstring home, jstring storage, jstring libs, jstring key) {
    const char *runtime = (*env)->GetStringUTFChars(env, home, NULL);
    PyConfig config;
    PyConfig_InitIsolatedConfig(&config);
    config.install_signal_handlers = 0;
    PyStatus status = PyConfig_SetBytesString(&config, &config.home, runtime);
    (*env)->ReleaseStringUTFChars(env, home, runtime);
    if (!PyStatus_Exception(status)) status = Py_InitializeFromConfig(&config);
    PyConfig_Clear(&config);
    if (PyStatus_Exception(status)) {
        (*env)->ThrowNew(env, (*env)->FindClass(env,"java/lang/IllegalStateException"), "Offline runtime initialization failed");
        return 0;
    }
    PyObject *module = PyImport_ImportModule("mobile");
    const char *root = (*env)->GetStringUTFChars(env, storage, NULL);
    const char *native = (*env)->GetStringUTFChars(env, libs, NULL);
    const char *token = (*env)->GetStringUTFChars(env, key, NULL);
    PyObject *result = module ? PyObject_CallMethod(module,"start","sss",root,native,token) : NULL;
    (*env)->ReleaseStringUTFChars(env, storage, root);
    (*env)->ReleaseStringUTFChars(env, libs, native);
    (*env)->ReleaseStringUTFChars(env, key, token);
    int port = result ? (int)PyLong_AsLong(result) : 0;
    if (!port) {
        PyErr_Print();
        (*env)->ThrowNew(env, (*env)->FindClass(env,"java/lang/IllegalStateException"), "The local dashboard could not start");
    }
    Py_XDECREF(result);
    Py_XDECREF(module);
    PyEval_SaveThread();
    return port;
}
