#import <AppKit/AppKit.h>
BOOL EchoPlayMedia(NSView *host, NSURL *mediaURL, NSURL *vlcApp);
BOOL EchoPlayEpisode(NSView *host, NSURL *mediaURL, NSURL *vlcApp, int64_t start, void (^progress)(int64_t,int64_t,BOOL));
