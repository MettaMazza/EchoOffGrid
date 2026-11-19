#include "sherpa-api.h"

const SherpaOnnxOfflineTts *voice_init(const char *model, const char *voices,
        const char *tokens, const char *data, const char *lexicon) {
    SherpaOnnxOfflineTtsConfig config = {0};
    config.model.kokoro.model = model;
    config.model.kokoro.voices = voices;
    config.model.kokoro.tokens = tokens;
    config.model.kokoro.data_dir = data;
    config.model.kokoro.lexicon = lexicon;
    config.model.kokoro.lang = "en-us";
    config.model.kokoro.length_scale = 1.0;
    config.model.num_threads = 3;
    config.model.provider = "cpu";
    config.max_num_sentences = 1;
    return SherpaOnnxCreateOfflineTts(&config);
}

int voice_render(const SherpaOnnxOfflineTts *engine, const char *text, const char *file) {
    const SherpaOnnxGeneratedAudio *audio = SherpaOnnxOfflineTtsGenerate(engine,text,21,1.0f);
    if (!audio) return 0;
    int ok = audio->n > 0 && SherpaOnnxWriteWave(audio->samples,audio->n,audio->sample_rate,file);
    SherpaOnnxDestroyOfflineTtsGeneratedAudio(audio);
    return ok;
}
