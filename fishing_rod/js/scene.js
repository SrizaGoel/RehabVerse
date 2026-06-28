import * as THREE from 'three';
import { Water } from "./water.js";
import { FishManager } from "./FishManager.js";
const scene = new THREE.Scene();
scene.background = new THREE.Color(0xbfdfff);
// const camera = new THREE.PerspectiveCamera(75, window.innerWidth / (window.innerHeight * 0.7), 0.1, 1000);
const container = document.querySelector(".game-area");
const camera = new THREE.PerspectiveCamera(
    75,
    container.clientWidth / container.clientHeight,
    0.1,
    1000
);

camera.position.set(
    0,
    20,
    45
);

camera.lookAt(
    0,
    0,
    0
);
// const renderer = new THREE.WebGLRenderer({ canvas: document.getElementById("gameCanvas"), antialias: true });
// renderer.setSize(window.innerWidth, window.innerHeight * 0.7);
// renderer.setPixelRatio(window.devicePixelRatio);
const sun = new THREE.DirectionalLight(
    0xffffff,
    5
);


const renderer = new THREE.WebGLRenderer({
    canvas: document.getElementById("gameCanvas"),
    antialias: true
});

renderer.setSize(
    container.clientWidth,
    container.clientHeight
);

renderer.setPixelRatio(window.devicePixelRatio);
sun.position.set(
    100,
    100,
    50
);

scene.add(sun);

scene.add(new THREE.AmbientLight(0xffffff, 0.35));

// function animate() {

//     requestAnimationFrame(animate);

//     water.material.uniforms["time"].value += 1 / 60;

//     renderer.render(
//         scene,
//         camera
//     );

// }

const waterGeometry = new THREE.PlaneGeometry(
    1000,
    1000
);
const textureLoader = new THREE.TextureLoader();

const waterNormals = textureLoader.load(
    "./assets/textures/waternormals.jpg",
    function (texture) {

        texture.wrapS = THREE.RepeatWrapping;
        texture.wrapT = THREE.RepeatWrapping;

    }
);
const water = new Water(

    waterGeometry,

    {

        textureWidth: 512,

        textureHeight: 512,

        waterNormals: waterNormals,

        sunDirection: sun.position.clone().normalize(),

        sunColor: 0xffffff,

        waterColor: 0x1e4f7a,

        distortionScale: 3.5,

        fog: false

    }

);
const fishManager =
    new FishManager(scene);

fishManager.createFish(5);
water.rotation.x = -Math.PI / 2;
scene.add(water);
// animate();
window.addEventListener("resize", () => {

    renderer.setSize(
        container.clientWidth,
        container.clientHeight
    );

    camera.aspect =
        container.clientWidth /
        container.clientHeight;

    camera.updateProjectionMatrix();

});
const clock =
new THREE.Clock();

function animate(){

    requestAnimationFrame(animate);

    const delta =
        clock.getDelta();

    const time =
        clock.getElapsedTime();

    water.material.uniforms["time"].value+=delta;

    fishManager.update(time,delta);

    renderer.render(scene,camera);

}


const weekConfig = {

    1:{
        visibleFish:5,
        catchesRequired:5
    },

    2:{
        visibleFish:6,
        catchesRequired:8
    },

    3:{
        visibleFish:7,
        catchesRequired:10
    },

    4:{
        visibleFish:8,
        catchesRequired:12
    }

};
animate();