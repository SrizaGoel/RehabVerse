import * as THREE from "three";

export class Fish {

    constructor(scene){

        this.scene = scene;

        this.group = new THREE.Group();

        //---------------- Body ----------------//

        const body = new THREE.Mesh(

            new THREE.SphereGeometry(0.45,24,24),

            new THREE.MeshStandardMaterial({
                color:0xff8844
            })

        );

        body.scale.set(1.5,1,0.8);

        this.group.add(body);

        //---------------- Tail ----------------//

        const tail = new THREE.Mesh(

            new THREE.ConeGeometry(0.22,0.45,16),

            new THREE.MeshStandardMaterial({
                color:0xff6633
            })

        );

        tail.rotation.z = Math.PI/2;
        tail.position.x = -0.7;

        this.group.add(tail);

        //---------------- Eye ----------------//

        const eye = new THREE.Mesh(

            new THREE.SphereGeometry(0.04),

            new THREE.MeshBasicMaterial({
                color:0xffffff
            })

        );

        eye.position.set(0.45,0.12,0.25);

        this.group.add(eye);

        scene.add(this.group);

        //----------------------------------//

        this.speed = 1 + Math.random();

        this.direction =
            Math.random()>0.5 ? 1 : -1;

        this.boundary = 18;

        this.offset =
            Math.random()*100;

        this.state = "swimming";

    }

    spawn(){

        this.group.position.set(

            (Math.random()-0.5)*30,

            0.5+Math.random()*0.5,

            (Math.random()-0.5)*12

        );

    }

    update(time,delta){

        if(this.state!="swimming")
            return;

        this.group.position.x +=
            this.speed*this.direction*delta;

        this.group.position.y =
            0.6+
            Math.sin(
                time*2+
                this.offset
            )*0.08;

        if(this.direction==1){

            this.group.rotation.y =
                -Math.PI/2;

        }

        else{

            this.group.rotation.y =
                Math.PI/2;

        }

        if(
            this.group.position.x>
            this.boundary
        ){

            this.direction=-1;

        }

        if(
            this.group.position.x<
            -this.boundary
        ){

            this.direction=1;

        }

    }

}