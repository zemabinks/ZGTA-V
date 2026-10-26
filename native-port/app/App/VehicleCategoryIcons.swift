import UIKit

enum VehicleCategoryIcons {
    private static var cache: [String: UIImage] = [:]

    static func image(named name: String) -> UIImage? {
        if let image = cache[name] { return image }
        let image: UIImage?
        if name.hasPrefix("zgta."), VehicleCategoryArtwork.names.contains(String(name.dropFirst(5))) {
            image = UIGraphicsImageRenderer(size: CGSize(width: 32, height: 32)).image { renderer in
                renderer.cgContext.setStrokeColor(UIColor.white.cgColor)
                VehicleCategoryArtwork.draw(String(name.dropFirst(5)), in: renderer.cgContext)
            }.withRenderingMode(.alwaysTemplate)
        } else {
            // A missing category glyph must never silently turn into a car.
            image = UIImage(systemName: name) ?? UIImage(systemName: "square.grid.2x2.fill")
        }
        cache[name] = image
        return image
    }
}
