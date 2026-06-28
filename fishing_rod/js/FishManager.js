import { Fish } from "./Fish.js";

export class FishManager{

    constructor(scene){

        this.scene = scene;

        this.fishes = [];

        this.targetFish = null;

    }

    createFish(count){

        for(let i=0;i<count;i++){

            const fish =
                new Fish(this.scene);

            fish.spawn();

            this.fishes.push(fish);

        }

    }

    update(time,delta){

        for(const fish of this.fishes){

            fish.update(time,delta);

        }

    }

    chooseTarget(){

        if(this.targetFish)
            return;

        const index =
            Math.floor(
                Math.random()*
                this.fishes.length
            );

        this.targetFish =
            this.fishes[index];

        this.targetFish.state =
            "target";

    }

    catchTarget(){

        if(!this.targetFish)
            return;

        this.targetFish.group.visible=false;

        const i =
            this.fishes.indexOf(
                this.targetFish
            );

        this.fishes.splice(i,1);

        this.targetFish=null;

    }

}