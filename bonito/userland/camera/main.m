// Camera: the phone's cameras for the hosted iOS (docs/CAMERA.md). Apple's Camera app needs Apple's ISP; this one shows the frames the
// Linux host writes into /dev/sweetcam (camfile.h) and saves them to Photos.
#import <UIKit/UIKit.h>
#include <fcntl.h>
#include <unistd.h>
#include "../../../host/camfile.h"

@interface CameraController : UIViewController
@end

@implementation CameraController {
	int _fd;
	uint32_t _camera, _beat, _seq;
	UIImageView *_view;
	UILabel *_message;
	UIButton *_shutter, *_flip;
	CADisplayLink *_link;
	NSDate *_lastFrame;
}

- (void)viewDidLoad {
	[super viewDidLoad];
	self.view.backgroundColor = UIColor.blackColor;
	_camera = 1;
	_view = [[UIImageView alloc] init];
	_view.contentMode = UIViewContentModeScaleAspectFit;
	[self.view addSubview:_view];
	_message = [[UILabel alloc] init];
	_message.textColor = UIColor.whiteColor;
	_message.textAlignment = NSTextAlignmentCenter;
	_message.numberOfLines = 0;
	[self.view addSubview:_message];
	_shutter = [UIButton buttonWithType:UIButtonTypeCustom];
	_shutter.backgroundColor = UIColor.whiteColor;
	_shutter.layer.cornerRadius = 36;
	_shutter.layer.borderWidth = 5;
	_shutter.layer.borderColor = UIColor.grayColor.CGColor;
	_shutter.accessibilityLabel = @"Take Photo";
	[_shutter addTarget:self action:@selector(take) forControlEvents:UIControlEventTouchUpInside];
	[self.view addSubview:_shutter];
	_flip = [UIButton buttonWithType:UIButtonTypeSystem];
	[_flip setTitle:@"Flip" forState:UIControlStateNormal];
	_flip.titleLabel.font = [UIFont systemFontOfSize:20 weight:UIFontWeightSemibold];
	_flip.tintColor = UIColor.whiteColor;
	[_flip addTarget:self action:@selector(flip) forControlEvents:UIControlEventTouchUpInside];
	[self.view addSubview:_flip];
	_fd = open("/dev/sweetcam", O_RDWR);
	if (_fd < 0)
		_message.text = @"No camera device (/dev/sweetcam).";
	_lastFrame = [NSDate date];
	_link = [CADisplayLink displayLinkWithTarget:self selector:@selector(tick)];
	_link.preferredFramesPerSecond = 20;
	[_link addToRunLoop:NSRunLoop.mainRunLoop forMode:NSRunLoopCommonModes];
}

- (void)viewDidLayoutSubviews {
	[super viewDidLayoutSubviews];
	CGRect b = self.view.bounds;
	CGFloat w = b.size.width, h = b.size.height, bottom = self.view.safeAreaInsets.bottom, top = self.view.safeAreaInsets.top;
	_view.frame = CGRectMake(0, top, w, w * 4 / 3);
	_message.frame = CGRectInset(_view.frame, 24, 24);
	_shutter.frame = CGRectMake(w / 2 - 36, h - bottom - 100, 72, 72);
	_flip.frame = CGRectMake(w - 96, h - bottom - 86, 72, 44);
}

- (UIStatusBarStyle)preferredStatusBarStyle {
	return UIStatusBarStyleLightContent;
}

- (void)tick {
	if (_fd < 0 || UIApplication.sharedApplication.applicationState != UIApplicationStateActive)
		return;		// (the host switches the camera off when the count stands still)
	struct camf_request q = { CAMF_QMAGIC, _camera, ++_beat };
	pwrite(_fd, &q, sizeof(q), CAMF_REQUEST);
	struct camf_state s;
	if (pread(_fd, &s, sizeof(s), CAMF_STATE) != sizeof(s) || s.magic != CAMF_SMAGIC || s.seq == _seq || s.camera != _camera ||
	    s.slot > 1 || !s.width || !s.height || (uint64_t)s.width * s.height * 4 > CAMF_SLOT) {
		if (-_lastFrame.timeIntervalSinceNow > 6)
			_message.text = @"No picture from the camera.";
		return;
	}
	size_t bytes = (size_t)s.width * s.height * 4, done = 0;
	NSMutableData *pixels = [NSMutableData dataWithLength:bytes];
	while (done < bytes) {
		ssize_t n = pread(_fd, (char *)pixels.mutableBytes + done, bytes - done, CAMF_PIXELS + (off_t)s.slot * CAMF_SLOT + done);
		if (n <= 0)
			return;
		done += n;
	}
	_seq = s.seq;
	CGDataProviderRef provider = CGDataProviderCreateWithCFData((__bridge CFDataRef)pixels);
	CGColorSpaceRef space = CGColorSpaceCreateDeviceRGB();
	CGImageRef image = CGImageCreate(s.width, s.height, 8, 32, (size_t)s.width * 4, space,
	    kCGBitmapByteOrder32Little | (CGBitmapInfo)kCGImageAlphaNoneSkipFirst, provider, NULL, false, kCGRenderingIntentDefault);
	_view.image = [UIImage imageWithCGImage:image];
	CGImageRelease(image);
	CGColorSpaceRelease(space);
	CGDataProviderRelease(provider);
	_lastFrame = [NSDate date];
	_message.text = nil;
}

- (void)flip {
	_camera = 3 - _camera;
	_view.image = nil;
	_lastFrame = [NSDate date];
}

- (void)take {
	UIImage *picture = _view.image;
	if (!picture)
		return;
	_view.alpha = 0.2;
	[UIView animateWithDuration:0.4 animations:^{ self->_view.alpha = 1; }];
	UIImageWriteToSavedPhotosAlbum(picture, self, @selector(saved:error:context:), NULL);
}

- (void)saved:(UIImage *)image error:(NSError *)error context:(void *)context {
	if (error)
		_message.text = [NSString stringWithFormat:@"Not saved: %@", error.localizedDescription];
}

@end

@interface AppDelegate : UIResponder <UIApplicationDelegate>
@property (nonatomic, strong) UIWindow *window;
@end

@implementation AppDelegate
- (BOOL)application:(UIApplication *)application didFinishLaunchingWithOptions:(NSDictionary *)options {
	self.window = [[UIWindow alloc] initWithFrame:UIScreen.mainScreen.bounds];
	self.window.rootViewController = [[CameraController alloc] init];
	[self.window makeKeyAndVisible];
	return YES;
}
@end

int main(int argc, char **argv) {
	@autoreleasepool {
		return UIApplicationMain(argc, argv, nil, @"AppDelegate");
	}
}
