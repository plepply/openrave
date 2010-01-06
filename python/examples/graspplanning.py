#!/usr/bin/env python
# Copyright (C) 2009-2010 Rosen Diankov (rosen.diankov@gmail.com)
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License. 
import time,traceback
from openravepy import *
from openravepy.interfaces import BaseManipulation, TaskManipulation
from openravepy.examples.grasping import Grasping
from numpy import *
import numpy

class GraspPlanning(metaclass.AutoReloader):
    def __init__(self,env,robot,randomize=False,dests=None,switchpatterns=None):
        self.envreal = env
        self.robot = robot
        self.switchpatterns = switchpatterns
        with self.envreal:
            self.basemanip = BaseManipulation(env,robot)
            self.taskmanip = TaskManipulation(env,robot)
            self.updir = array((0,0,1))

            # find all the bodies to manipulate
            print 'searching for graspable objects...'
            self.graspables = []
            for target in self.envreal.GetBodies():
                if not target.IsRobot():
                    grasping = Grasping(env,robot,target)
                    if grasping.loadGrasps():
                        print '%s is graspable'%target.GetName()
                        if randomize:
                            Tbody = target.GetTransform()
                            for iter in range(5):
                                Tnew = array(Tbody)
                                Tnew[0,3] += -0.1 + 0.2 * random.rand()
                                Tnew[1,3] += -0.1 + 0.2 * random.rand()
                                target.SetTransform(Tnew)
                                if not self.envreal.CheckCollision(target):
                                    Tbody = Tnew
                                    break
                            target.SetTransform(Tbody)
                        self.graspables.append([grasping,dests])

            if randomize: # randomize the robot
                Trobot = self.robot.GetTransform()
                for iter in range(5):
                    Tnew = array(Trobot)
                    Tnew[0,3] += -0.1 + 0.2 * random.rand()
                    Tnew[1,3] += -0.1 + 0.2 * random.rand()
                    self.robot.SetTransform(Tnew)
                    if not self.envreal.CheckCollision(self.robot):
                        Trobot = Tnew
                        break
                self.robot.SetTransform(Trobot)

            if dests is None:
                tablename = 'table'
                table = self.envreal.GetKinBody(tablename)
                if table is not None:
                    self.setRandomDestinations(table)
                else:
                    print 'could not find %s'%tablename

    def setRandomDestinations(self, table,randomize=False):
        with self.envreal:
            print 'searching for destinations on %s...'%table.GetName()
            Ttable = table.GetTransform()
            table.SetTransform(eye(4))
            ab = table.ComputeAABB()
            table.SetTransform(Ttable)
            p = ab.pos()
            e = numpy.minimum(ab.extents(),array((0.2,0.2,1)))
            Nx = floor(2*e[0]/0.1)
            Ny = floor(2*e[1]/0.1)
            X = []
            Y = []
            if randomize:
                for x in arange(Nx):
                    X = r_[X, random.rand(Ny)*0.5/(Nx+1) + (x+1)/(Nx+1)]
                    Y = r_[Y, random.rand(Ny)*0.5/(Ny+1) + arange(0.5,Ny,1.0)/(Ny+1)]
            else:
                for x in arange(Nx):
                    X = r_[X, tile((x+1)/(Nx+1),Ny)]
                    Y = r_[Y, arange(0.5,Ny,1.0)/(Ny+1)]
            translations = c_[p[0]-e[0]*2*e[0]*X,p[1]-e[1]+2*e[1]*Y,tile(p[2]+e[2],len(X))]
            Trolls = [matrixFromAxisAngle(array((0,0,1)),roll) for roll in arange(0,2*pi,pi/2)] + [matrixFromAxisAngle(array((1,0,0)),roll) for roll in [pi/2,pi,1.5*pi]]

            for graspable in self.graspables:
                graspable[0].target.Enable(False)
            for graspable in self.graspables:
                if graspable[1] is not None:
                    continue
                body = graspable[0].target
                Torg = body.GetTransform()
                Torg[0:3,3] = 0 # remove translation
                with KinBodyStateSaver(body):
                    body.Enable(True)
                    dests = []
                    for translation in translations:
                        for Troll in Trolls:
                            Troll[0:3,3] = translation
                            body.SetTransform(dot(Ttable, dot(Troll, Torg)))
                            if not self.envreal.CheckCollision(body):
                                dests.append(body.GetTransform())
                    print len(dests)
                    graspable[1] = dests
            for graspable in self.graspables:
                graspable[0].target.Enable(True)

    def viewDestinations(self,graspable,delay=0.5):
        with graspable[0].target:
            for T in graspable[1]:
                graspable[0].target.SetTransform(T)
                graspable[0].target.GetEnv().UpdatePublishedBodies()
                time.sleep(delay)
            
    def graspAndPlaceObject(self,grasping,dests):
        env = self.envreal#.CloneSelf(CloningOptions.Bodies)
        istartgrasp = 0
        while istartgrasp < len(self.grasping.grasps):
            goals,graspindex,searchtime,trajdata = self.taskmanip.GraspPlanning(graspindices=grasping.graspindices,grasps=grasping.grasps[istartgrasp:],
                                                                                target=grasping.target,approachoffset=0.02,destposes=dests,
                                                                                seedgrasps = 3,seeddests=8,seedik=1,maxiter=1000,
                                                                                randomgrasps=True,randomdests=True,switchpatterns=self.switchpatterns)
            istartgrasp = grasping+1
            print graspindex, searchtime
            self.robot.WaitForController(0)
            break

    def performGraspPlanning(self):
        pass

def run():
    env = Environment()
    try:
        env.Load('data/lab1.env.xml')
        env.SetViewer('qtcoin')
        robot = env.GetRobots()[0]
        self = GraspPlanning(env,robot)
    finally:
        env.Destroy()

if __name__ == "__main__":
    run()
