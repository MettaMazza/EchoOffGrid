#import "MediaPlayer.h"
#import <Security/Security.h>
#import <dlfcn.h>

typedef struct {
    void *(*create)(int,const char *const *);
    void (*release)(void *);
    void *(*location)(void *,const char *);
    void (*releaseMedia)(void *);
    void *(*player)(void *);
    void (*releasePlayer)(void *);
    void (*setView)(void *,void *);
    int (*play)(void *);
    void (*pause)(void *);
    void (*stop)(void *);
    float (*position)(void *);
    void (*seek)(void *,float);
    int (*playing)(void *);
    int (*state)(void *);
} PlayerAPI;

@interface EchoMovieView : NSView
@property PlayerAPI api;
@property void *instance;
@property void *player;
@property NSView *screen;
@property NSSlider *slider;
@property NSButton *toggle;
@property NSTimer *timer;
@end

@implementation EchoMovieView
- (void)closeMovie {
    [self.timer invalidate];
    self.timer = nil;
    if (self.player) {
        self.api.stop(self.player);
        self.api.setView(self.player,NULL);
        self.api.releasePlayer(self.player);
        self.player = NULL;
    }
    if (self.instance) {
        self.api.release(self.instance);
        self.instance = NULL;
    }
    [self removeFromSuperview];
}
- (void)viewDidMoveToWindow {
    [super viewDidMoveToWindow];
    if (!self.window && self.player) [self closeMovie];
}
- (void)toggleFullscreen { [self.window toggleFullScreen:self]; }
- (void)togglePlayback {
    if (self.api.playing(self.player)) self.api.pause(self.player);
    else self.api.play(self.player);
}
- (void)seek { self.api.seek(self.player,self.slider.floatValue); }
- (void)refresh {
    if (self.api.state(self.player)==7) { self.toggle.title=@"Retry playback"; return; }
    self.toggle.title=self.api.playing(self.player)?@"Pause":@"Play";
    if (!self.slider.cell.isHighlighted) self.slider.floatValue=self.api.position(self.player);
}
@end

BOOL EchoPlayMedia(NSView *host, NSURL *mediaURL, NSURL *vlcApp) {
    NSURL *library=[vlcApp URLByAppendingPathComponent:@"Contents/MacOS/lib/libvlc.5.dylib"];
    // Load native code only from a signed VideoLAN distribution.
    SecStaticCodeRef code=NULL;
    SecRequirementRef requirement=NULL;
    OSStatus result=SecStaticCodeCreateWithPath((__bridge CFURLRef)vlcApp,kSecCSDefaultFlags,&code);
    if (result==errSecSuccess) result=SecRequirementCreateWithString(CFSTR("anchor apple generic and identifier \"org.videolan.vlc\" and certificate leaf[subject.OU] = \"75GAHG3SZQ\""),kSecCSDefaultFlags,&requirement);
    if (result==errSecSuccess) result=SecStaticCodeCheckValidity(code,kSecCSCheckNestedCode,requirement);
    if (code) CFRelease(code);
    if (requirement) CFRelease(requirement);
    if (result!=errSecSuccess) return NO;
    NSURL *core=[library.URLByDeletingLastPathComponent URLByAppendingPathComponent:@"libvlccore.9.dylib"];
    if (!dlopen(core.fileSystemRepresentation,RTLD_NOW|RTLD_LOCAL)) return NO;
    void *lib=dlopen(library.fileSystemRepresentation,RTLD_NOW|RTLD_LOCAL);
    if (!lib) return NO;
    PlayerAPI api={0};
#define LOAD(field,name) if (!(api.field=dlsym(lib,"libvlc_" name))) return NO;
    LOAD(create,"new") LOAD(release,"release") LOAD(location,"media_new_location")
    LOAD(releaseMedia,"media_release") LOAD(player,"media_player_new_from_media")
    LOAD(releasePlayer,"media_player_release") LOAD(setView,"media_player_set_nsobject")
    LOAD(play,"media_player_play") LOAD(pause,"media_player_pause") LOAD(stop,"media_player_stop")
    LOAD(position,"media_player_get_position") LOAD(seek,"media_player_set_position")
    LOAD(playing,"media_player_is_playing") LOAD(state,"media_player_get_state")
#undef LOAD
    EchoMovieView *view=[[EchoMovieView alloc] initWithFrame:host.bounds];
    view.api=api;
    const char *opts[]={"--ignore-config","--no-video-title-show","--no-media-library"};
    NSURL *plugins=[vlcApp URLByAppendingPathComponent:@"Contents/MacOS/plugins"];
    setenv("VLC_PLUGIN_PATH",plugins.fileSystemRepresentation,1);
    view.instance=api.create(3,opts);
    if (!view.instance) return NO;
    void *media=api.location(view.instance,mediaURL.absoluteString.UTF8String);
    if (media) {view.player=api.player(media);api.releaseMedia(media);}
    if (!view.player) {[view closeMovie];return NO;}
    view.autoresizingMask=NSViewWidthSizable|NSViewHeightSizable;
    view.wantsLayer=YES;view.layer.backgroundColor=NSColor.blackColor.CGColor;
    view.screen=[[NSView alloc] initWithFrame:NSMakeRect(0,52,host.bounds.size.width,MAX(1,host.bounds.size.height-52))];
    view.screen.autoresizingMask=NSViewWidthSizable|NSViewHeightSizable;
    [view addSubview:view.screen];
    NSButton *back=[NSButton buttonWithTitle:@"Back to video" target:view action:@selector(closeMovie)];
    view.toggle=[NSButton buttonWithTitle:@"Pause" target:view action:@selector(togglePlayback)];
    view.slider=[NSSlider sliderWithValue:0 minValue:0 maxValue:1 target:view action:@selector(seek)];
    [view.slider setAccessibilityLabel:@"Playback position"];
    NSButton *wide=[NSButton buttonWithTitle:@"Toggle fullscreen" target:view action:@selector(toggleFullscreen)];
    NSStackView *bar=[NSStackView stackViewWithViews:@[back,view.toggle,view.slider,wide]];
    bar.distribution=NSStackViewDistributionFill;
    [view.slider.widthAnchor constraintGreaterThanOrEqualToConstant:100].active=YES;
    [view.slider setContentHuggingPriority:NSLayoutPriorityDefaultLow forOrientation:NSLayoutConstraintOrientationHorizontal];
    bar.frame=NSMakeRect(12,10,MAX(1,host.bounds.size.width-24),30);
    bar.autoresizingMask=NSViewWidthSizable;
    [view addSubview:bar];[host addSubview:view];
    api.setView(view.player,(__bridge void *)view.screen);
    if (api.play(view.player)!=0) {[view closeMovie];return NO;}
    view.timer=[NSTimer scheduledTimerWithTimeInterval:.35 target:view selector:@selector(refresh) userInfo:nil repeats:YES];
    return YES;
}
