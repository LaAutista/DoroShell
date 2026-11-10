#include "../wallpaper/dorovideotransport.h"
#include <cassert>
#include <vector>
int main() {
    std::vector<unsigned char> padded(3*32,0xee);
    QImage image(padded.data(),5,3,32,QImage::Format_RGB32);
    for(int y=0;y<3;y++) for(int x=0;x<5;x++) image.setPixel(x,y,qRgb(20*x,30*y,90));
    std::vector<char> output(5*3*4+16,char(0xcc));
    doroCopyVideoPixels(output.data(),image);
    QImage copied(reinterpret_cast<const unsigned char*>(output.data()),5,3,20,QImage::Format_RGB32);
    for(int y=0;y<3;y++) for(int x=0;x<5;x++) assert(copied.pixel(x,y)==image.pixel(x,y));
    for(int i=60;i<76;i++) assert(output[i]==char(0xcc));
}
