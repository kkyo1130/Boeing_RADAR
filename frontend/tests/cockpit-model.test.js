import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

test('cockpit GLB is self-contained with aligned embedded PNG artwork and valid mesh buffers',()=>{
 const bytes=readFileSync(new URL('../public/models/cockpit.glb',import.meta.url));
 assert.equal(bytes.toString('ascii',0,4),'glTF');assert.equal(bytes.readUInt32LE(4),2);assert.equal(bytes.readUInt32LE(8),bytes.length);
 const jsonLength=bytes.readUInt32LE(12),gltf=JSON.parse(bytes.toString('utf8',20,20+jsonLength));
 const offset=20+jsonLength,bin=bytes.subarray(offset+8);assert.equal(bytes.readUInt32LE(offset+4),0x004e4942);assert.equal(gltf.buffers[0].byteLength,bin.length);
 assert.ok(gltf.images.length>=7);assert.ok(gltf.meshes.length>100);
 for(const image of gltf.images){
  assert.equal(image.uri,undefined);assert.equal(image.mimeType,'image/png');
  const view=gltf.bufferViews[image.bufferView];assert.equal(view.byteOffset%4,0);
  assert.equal(bin.subarray(view.byteOffset,view.byteOffset+8).toString('hex'),'89504e470d0a1a0a');
 }
 for(const view of gltf.bufferViews){assert.ok((view.byteOffset||0)+view.byteLength<=bin.length);}
 for(const accessor of gltf.accessors){assert.ok(accessor.count>0);assert.ok(gltf.bufferViews[accessor.bufferView]);}
 for(const material of gltf.materials){const texture=material.pbrMetallicRoughness?.baseColorTexture;if(texture)assert.ok(gltf.images[gltf.textures[texture.index].source]);}
});
