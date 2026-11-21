import AVFoundation
import AppKit
import PDFKit

@main struct MakePoster {
    static func hasPicture(_ image:CGImage)->Bool {
        var pixels=[UInt8](repeating:0,count:256)
        return pixels.withUnsafeMutableBytes { memory in
            guard let context=CGContext(data:memory.baseAddress,width:16,height:16,bitsPerComponent:8,
                bytesPerRow:16,space:CGColorSpaceCreateDeviceGray(),bitmapInfo:CGImageAlphaInfo.none.rawValue)
            else{return true}
            context.draw(image,in:CGRect(x:0,y:0,width:16,height:16))
            let values=memory.bindMemory(to:UInt8.self)
            return Int(values.max() ?? 0)-Int(values.min() ?? 0)>=24 && values.filter{$0>28}.count>=20
        }
    }

    static func main() async throws {
        let args=CommandLine.arguments
        if args.count==4 && args[1]=="--metadata" {
            let url=URL(fileURLWithPath:args[2])
            let destination=URL(fileURLWithPath:args[3])
            var title=""
            var image:NSImage?
            if url.pathExtension.lowercased()=="pdf",let pdf=PDFDocument(url:url){
                title=pdf.documentAttributes?[PDFDocumentAttribute.titleAttribute] as? String ?? ""
                image=pdf.page(at:0)?.thumbnail(of:NSSize(width:360,height:480),for:.mediaBox)
            } else {
                let asset=AVURLAsset(url:url)
                for field in (try? await asset.load(.commonMetadata)) ?? [] {
                    if field.commonKey == .commonKeyTitle {title=(try? await field.load(.stringValue)) ?? ""}
                    if field.commonKey == .commonKeyArtwork,let bytes=try? await field.load(.dataValue),bytes.count<=8*1024*1024 {image=NSImage(data:bytes)}
                }
            }
            if let image,let bytes=image.tiffRepresentation,let bitmap=NSBitmapImageRep(data:bytes),
               let cover=bitmap.representation(using:.jpeg,properties:[.compressionFactor:0.85]) {try cover.write(to:destination,options:.atomic)}
            print(title);return
        }
        guard CommandLine.arguments.count == 3 else { exit(2) }
        let source = AVURLAsset(url: URL(fileURLWithPath: CommandLine.arguments[1]))
        let generator = AVAssetImageGenerator(asset: source)
        generator.maximumSize = CGSize(width: 800, height: 450)
        generator.appliesPreferredTrackTransform = true
        let duration = try await source.load(.duration).seconds
        var poster:CGImage?
        let times=[min(2,max(0,duration*0.1)),5.5,14,duration/8,duration/3,duration/2]
        for time in times where time.isFinite {
            let at=CMTime(seconds:max(0,min(time,duration-0.05)),preferredTimescale:600)
            guard let result=try? await generator.image(at:at) else{continue}
            if hasPicture(result.image){poster=result.image;break}
            if poster==nil{poster=result.image}
        }
        guard let poster else{exit(1)}
        let bitmap=NSBitmapImageRep(cgImage:poster)
        guard let data = bitmap.representation(using: .jpeg, properties: [.compressionFactor: 0.83]) else { exit(1) }
        try data.write(to: URL(fileURLWithPath: CommandLine.arguments[2]), options: .atomic)
    }
}
