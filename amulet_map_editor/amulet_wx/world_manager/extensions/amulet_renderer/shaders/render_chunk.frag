# version 330
in vec2 fTexCoord;
in vec4 fTexOffset;

out vec4 outColor;

uniform sampler2D image;

void main(){
    outColor = texture(
    	image,
    	vec2(
			mix(fTexOffset.x, fTexOffset.z, mod(fTexCoord.x, 1.0)),
			mix(fTexOffset.y, fTexOffset.w, 1.0-mod(fTexCoord.y, 1.0))
		)
	);
}